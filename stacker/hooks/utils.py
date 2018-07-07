from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import os


def full_path(path):
    return os.path.abspath(os.path.expanduser(path))
