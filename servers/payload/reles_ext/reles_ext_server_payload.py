#!/usr/bin/python3

import argparse
import http.server
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
from os import path
from threading import Event
from urllib.parse import parse_qs, urlparse

import numpy as np
import reles_ext_mpsched as mpsched
import torch
from agent import Offline_Agent, Online_Agent
from gym import spaces
from naf_lstm import NAF_LSTM
from replay_memory import ReplayMemory

# structure and modulisation based on github.com/gaogogo/Experiment
CURRENT_DIR = pathlib.Path(__file__).parent.resolve()
TMP_DIR = CURRENT_DIR / "artifacts"


class MyHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with overwritten do_GET function to give information about start of file transfer
    and the socket fd to the online agent
    """

    def do_GET(self):
        sock = self.request
        agent = Online_Agent(
            fd=sock.fileno(),
            cfg=self.server.cfg,
            memory=self.server.replay_memory,
            event=self.server.event,
        )
        agent.start()
        self.server.event.set()

        file_size, file_name = self.parse_file_size()
        if file_size is None:
            self.send_error(400, "Bad Request: Invalid file size specifier")
            return

        file_path = self.create_file(file_size, file_name)
        print(f"File path: {file_path}")
        if file_path is None:
            self.send_error(500, "Internal Server Error: Failed to create file")
            return

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
    AGENT_FILE = str((TMP_DIR / cfg.get("nafcnn", "agent")).resolve())
    INTERVAL = cfg.getint("train", "interval")
    EPISODE = cfg.getint("train", "episode")
    BATCH_SIZE = cfg.getint("train", "batch_size")
    MAX_NUM_FLOWS = cfg.getint("env", "max_num_subflows")
    transfer_event = Event()
    CONTINUE_TRAIN = args.continue_train

    now = datetime.now().replace(microsecond=0)
    start_train = now.strftime("%Y-%m-%d %H:%M:%S")

    if os.path.exists(MEMORY_FILE) and CONTINUE_TRAIN:
        with open(MEMORY_FILE, "rb") as f:
            try:
                memory = pickle.load(f)
                f.close()
            except EOFError:
                print("memory EOF error not saved properly")
                memory = ReplayMemory(cfg.getint("replaymemory", "capacity"))
    else:
        memory = ReplayMemory(cfg.getint("replaymemory", "capacity"))

    if CONTINUE_TRAIN != 1 and os.path.exists(AGENT_FILE):
        os.makedirs("trained_models/", exist_ok=True)
        shutil.move(AGENT_FILE, "trained_models/agent" + start_train + ".pkl")
    if not os.path.exists(AGENT_FILE) or CONTINUE_TRAIN != 1:
        pathlib.Path(AGENT_FILE).parent.mkdir(parents=True, exist_ok=True)
        agent = NAF_LSTM(
            gamma=cfg.getfloat("nafcnn", "gamma"),
            tau=cfg.getfloat("nafcnn", "tau"),
            hidden_size=cfg.getint("nafcnn", "hidden_size"),
            num_inputs=MAX_NUM_FLOWS * 5,
            action_space=MAX_NUM_FLOWS,
        )  # 5 is the size of state space (TP,RTT,CWND,unACK,retrans)
        torch.save(agent, AGENT_FILE)

    off_agent = Offline_Agent(
        cfg=cfg, model=AGENT_FILE, memory=memory, event=transfer_event
    )
    off_agent.daemon = True
    server = ThreadedHTTPServer((IP, PORT), MyHTTPHandler)
    server.event = transfer_event
    server.cfg = cfg
    server.replay_memory = memory
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        while transfer_event.wait(timeout=60):  # only returns false in case of timeout
            if len(memory) > BATCH_SIZE and not off_agent.is_alive():
                off_agent.start()
            time.sleep(25)
            pass
        with open(MEMORY_FILE, "wb") as f:
            pickle.dump(memory, f)
            f.close()
    except (KeyboardInterrupt, SystemExit):
        with open(MEMORY_FILE, "wb") as f:
            pickle.dump(memory, f)
            f.close()


if __name__ == "__main__":
    main()
