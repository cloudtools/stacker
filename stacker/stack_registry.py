import logging

logger = logging.getLogger(__name__)

from collections import MutableMapping

from .util import convert_class_name


class DuplicateEntry(Exception):
    def __init__(self, key, kls):
        self.key = key
        self.kls = kls

    def __str__(self):
        return "Duplicate entry '%s'." % self.key


class StackRegistry(MutableMapping):
    def __init__(self):
        self.store = {}

    def __setitem__(self, key, value):
        if key in self:
            raise DuplicateEntry(key, value)
        self.store[key] = value

    def __getitem__(self, key):
        return self.store.__getitem__(key)

    def __delitem__(self, key):
        return self.store.__delitem__(key)

    def __iter__(self):
        return self.store.__iter__()

    def __len__(self):
        return self.store.__len__()

    def add(self, stack_class, name=None):
        if not name:
            name = convert_class_name(stack_class)
        self[name] = stack_class

# Common registry for all stacks
stack_registry = StackRegistry()
