import os


def full_path(path):
    return os.path.abspath(os.path.expanduser(path))
