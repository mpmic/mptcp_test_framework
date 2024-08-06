import os
from pathlib import Path

# os.chdir(Path(__file__).parent.resolve())


FILES = ["64kb.dat", "2mb.dat", "8mb.dat", "64mb.dat"]


def create_file(filename, size):
    with open(filename, "wb") as file:
        file.write(os.urandom(size))
    print(f"File '{filename}' created with size {size} bytes.")


for file in FILES:
    if file == "64kb.dat":
        create_file(file, 64 * 1024)
    elif file == "2mb.dat":
        create_file(file, 2 * 1024 * 1024)
    elif file == "8mb.dat":
        create_file(file, 8 * 1024 * 1024)
    elif file == "64mb.dat":
        create_file(file, 64 * 1024 * 1024)
