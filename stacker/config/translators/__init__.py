import yaml

from .kms import kms_simple_constructor
from .file import file_constructor

yaml.add_constructor('!kms', kms_simple_constructor)
yaml.add_constructor('!file', file_constructor)
