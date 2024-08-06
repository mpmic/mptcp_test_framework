#!/usr/bin/python3

import argparse
import http.server
import os
import pathlib
import re
import socketserver
from typing import Optional
from urllib.parse import parse_qs, urlparse

class MyHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):

        # Extract the requested file size from the query parameter
        file_size, file_name = self.parse_file_size()
        # print(f"File size: {file_size}, File Name: {file_name}")
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

    def create_file(self, file_size, file_name) -> Optional[pathlib.Path]:
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
    pass


def main():
    parser = argparse.ArgumentParser(description="Simple HTTP Server to send files")
    parser.add_argument("--ip", default="localhost", help="Server IP address")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument(
        "--debug", action="store_true", help="Enable remote debugging with debugpy"
    )
    args = parser.parse_args()

    if args.debug:

        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        print("Waiting for debugger to attach...")
        debugpy.wait_for_client()

    server_address = (args.ip, args.port)
    server = ThreadedHTTPServer(server_address, MyHTTPHandler)

    print(f"Starting server on {args.ip}:{args.port}")

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit) as e:
        print(f"{e} detected, exiting...")


if __name__ == "__main__":
    main()
