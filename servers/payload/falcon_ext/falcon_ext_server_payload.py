#!/usr/bin/python3

# structure and modulisation based on github.com/gaogogo/Experiment

import argparse
import http.server
import itertools
import multiprocessing
import os
import pathlib
import pickle
import re
import shutil
import socket
import socketserver
import sys
import threading
import time
from configparser import ConfigParser
from datetime import datetime
from threading import Event
from urllib.parse import parse_qs, urlparse

import falcon_ext_mpsched as mpsched
import numpy as np
import torch
from agent import Offline_Agent, Online_Agent
from DQN import DQN_Agent
from gym import spaces
from replay_memory import ReplayMemory

CURRENT_DIR = pathlib.Path(__file__).parent.resolve()
TMP_DIR = CURRENT_DIR / "artifacts"


class MyHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with overwritten do_GET function to give information about start of file transfer, socket fd and file 	size to the online agent"""

    def do_GET(self):
        self.server.event.set()
        sock = self.request

        self.server.agent.update_fd(sock.fileno())

        file_size, file_name = self.parse_file_size()
        if file_size is None:
            self.send_error(400, "Bad Request: Invalid file size specifier")
            return

        file_path = self.create_file(file_size, file_name)
        print(f"File path: {file_path}")
        if file_path is None:
            self.send_error(500, "Internal Server Error: Failed to create file")
            return

        self.server.agent.update_cfile_size(file_size)

        # Send the temporary file
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.send_header("Content-Disposition", f'attachment; filename="{file_name}"')
        self.end_headers()

        with file_path.open("rb") as file:
            self.wfile.write(file.read())

        print(f"Done sending {file_path}")

        self.server.event.clear()

    def parse_file_size(self):
        # Extract the file size specifier from the query parameter
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        file_size_specifier = query_params.get("filesize", [None])[0]

        if file_size_specifier:
            # Parse the file size specifier using iperf-like format
            match = re.match(r"^(\d+)([KMG])?$", file_size_specifier, re.IGNORECASE)
            if match:
                size_value = int(match.group(1))
                size_unit = match.group(2).upper() if match.group(2) else "B"

                if size_unit == "K":
                    file_size = size_value * 1024
                    file_name = f"{size_value}K.dat"
                elif size_unit == "M":
                    file_size = size_value * 1024 * 1024
                    file_name = f"{size_value}M.dat"
                elif size_unit == "G":
                    file_size = size_value * 1024 * 1024 * 1024
                    file_name = f"{size_value}G.dat"
                else:
                    file_size = size_value
                    file_name = f"{size_value}B.dat"

                return file_size, file_name

        return None, None

    def create_file(self, file_size, file_name):
        temp_dir = pathlib.Path("/tmp")
        file_path = temp_dir / file_name

        if not file_path.exists():
            try:
                with open(file_path, "wb") as f:
                    f.write(os.urandom(file_size))
            except IOError:
                return None

        return file_path


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """ThreadedHTTPServer class initialized with (IP,PORT),HTTPRequestHandler"""

    pass


def main():
    parser = argparse.ArgumentParser(description="Simple HTTP Server to send files")
    parser.add_argument("--ip", default="localhost", help="Server IP address")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument(
        "--continue_train",
        type=int,
        default=1,
        help="Continue training from previous state (0: No, 1: Yes)",
    )

    parser.add_argument(
        "--debug", action="store_true", help="Enable remote debugging with debugpy"
    )

    args = parser.parse_args()

    if args.debug:
        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        print("Waiting for debugger to attach...")
        debugpy.wait_for_client()

    cfg = ConfigParser()
    cfg.read(CURRENT_DIR / "config.ini")
    IP = args.ip
    PORT = args.port
    MEMORY_FILE = str((TMP_DIR / cfg.get("replaymemory", "memory")).resolve())
    AGENT_FILE = str((TMP_DIR / cfg.get("dqn", "agent")).resolve()) + "/"
    INTERVAL = cfg.getint("train", "interval")
    EPISODE = cfg.getint("train", "episode")
    BATCH_SIZE = cfg.getint("train", "batch_size")
    MAX_NUM_FLOWS = cfg.getint("train", "max_num_flows")
    K = cfg.getint("dqn", "k")
    transfer_event = Event()
    NUM_CHAR = cfg.getint("train", "num_characteristics")
    NUM_RANGES = cfg.getint("train", "num_ranges")
    CONTINUE_TRAIN = args.continue_train

    now = datetime.now().replace(microsecond=0)
    start_train = now.strftime("%Y-%m-%d %H:%M:%S")

    path_char = list(itertools.product(list(range(0, NUM_RANGES)), repeat=NUM_CHAR))
    ALL_CHAR = np.array(
        list(map(list, (itertools.product(path_char, repeat=MAX_NUM_FLOWS))))
    ).reshape((-1, MAX_NUM_FLOWS * NUM_CHAR))

    agent_name = []
    if CONTINUE_TRAIN != 1 and os.path.exists(AGENT_FILE):
        try:
            os.remove(MEMORY_FILE)
        except FileNotFoundError:
            print("MEMORY file does not exist yet")
        os.makedirs("trained_models/", exist_ok=True)
        shutil.move(
            AGENT_FILE, str(TMP_DIR / f"trained_models/meta_models_{start_train}")
        )

    os.makedirs(AGENT_FILE, exist_ok=True)
    for i in range(len(ALL_CHAR)):
        index = "".join(str(x) for x in ALL_CHAR[i])
        agent_name.append(AGENT_FILE + index + ".pkl")
        if not os.path.exists(agent_name[i]) or CONTINUE_TRAIN != 1:
            agent = DQN_Agent(
                hidden_size=3,
                num_inputs=4 * MAX_NUM_FLOWS,
                num_outputs=MAX_NUM_FLOWS,
                gamma=cfg.getfloat("dqn", "gamma"),
            )
            torch.save(agent, agent_name[i])

    online_process = Online_Agent(fd=0, cfg=cfg, event=transfer_event)
    online_process.daemon = True
    online_process.start()
    offline_process = Offline_Agent(cfg, transfer_event)
    offline_process.daemon = True
    offline_process.start()
    server = ThreadedHTTPServer((IP, PORT), MyHTTPHandler)
    server.event = transfer_event
    server.agent = online_process
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        while transfer_event.wait(timeout=60):  # only returns false in case of timeout
            time.sleep(25)
            pass
        if CONTINUE_TRAIN != 1:
            time.sleep(360)
    except (KeyboardInterrupt, SystemExit):
        print("exit")


if __name__ == "__main__":
    main()
