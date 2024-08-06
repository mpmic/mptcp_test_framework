#!/usr/bin/python3

import argparse
import json
import socket
import time


def download_file(
    server_ip,
    server_port,
    file_size_specifier,
    local_ip=None,
    timeout=15,
    max_retries=3,
):
    throughput = None
    retries = 0

    while retries < max_retries:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)  # Set the socket timeout
                if local_ip:
                    sock.bind(
                        (local_ip, 0)
                    )  # Bind to the specified local IP address and an ephemeral port
                sock.connect((server_ip, server_port))
                request = f"GET /?filesize={file_size_specifier} HTTP/1.1\r\nHost: {server_ip}\r\n\r\n"
                sock.sendall(request.encode())
                start_time = time.monotonic()

                total_bytes = 0
                while True:
                    data = sock.recv(8192)
                    if not data:
                        break
                    total_bytes += len(data)

                end_time = time.monotonic()
                duration = end_time - start_time
                throughput = (
                    total_bytes / duration / (1024 * 1024)
                )  # Throughput in MB/s
                return throughput  # Return the throughput if the download is successful
        except (socket.timeout, ConnectionError) as e:
            print(f"Connection error: {str(e)}. Retrying... (Attempt {retries + 1})")
            retries += 1

    raise ConnectionError(f"Max retries reached {max_retries}. Download failed.")


def main():
    parser = argparse.ArgumentParser(description="File Download Client")
    parser.add_argument("--server_ip", required=True, help="Server IP address")
    parser.add_argument(
        "--client_bind_ip", default=None, help="Local IP address to bind to (optional)"
    )
    parser.add_argument("--server_port", type=int, default=8000, help="Server port")
    parser.add_argument(
        "--filesize", required=True, help="File size specifier (e.g., 1M, 10K)"
    )
    parser.add_argument(
        "--iterations", type=int, default=1, help="Number of iterations"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable remote debugging with debugpy"
    )

    args = parser.parse_args()

    if args.debug:

        import debugpy

        debugpy.listen(("0.0.0.0", 5678))
        print("client_payload.py: Waiting for debugger to attach...")
        debugpy.wait_for_client()

    server_ip = args.server_ip
    server_port = args.server_port
    file_size_specifier = args.filesize
    num_iterations = args.iterations
    client_bind_ip = args.client_bind_ip

    throughputs = []

    for i in range(num_iterations):
        throughput = download_file(
            server_ip, server_port, file_size_specifier, client_bind_ip
        )
        throughputs.append(throughput)
        print(f"Iteration {i + 1}: Throughput = {throughput:.2f} MB/s")

    avg_throughput = sum(throughputs) / len(throughputs)
    print(f"\nAverage Throughput: {avg_throughput:.2f} MB/s")

    # Output the throughputs in JSON format with identifier
    output = {
        "iterations": num_iterations,
        "throughputs": throughputs,
        "average_throughput": avg_throughput,
    }
    print("\nJSON_OUTPUT_START")
    print(json.dumps(output, indent=4))
    print("JSON_OUTPUT_END")


if __name__ == "__main__":
    main()
