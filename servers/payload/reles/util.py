import contextlib
import fcntl


@contextlib.contextmanager
def locked_open(filename, mode="rb"):
    """
    A context manager that opens a file and applies an exclusive lock.
    The lock is released when exiting the context.

    :param filename: The name of the file to open
    :param mode: The mode in which to open the file (default is 'r' for read)
    """
    with open(filename, mode) as file:
        try:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            yield file
        finally:
            fcntl.flock(file.fileno(), fcntl.LOCK_UN)
