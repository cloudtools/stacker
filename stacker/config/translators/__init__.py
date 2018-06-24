from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import yaml

from .kms import kms_simple_constructor

yaml.add_constructor('!kms', kms_simple_constructor)
