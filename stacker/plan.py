import copy
from collections import (
    OrderedDict,
    Iterable,
)
import logging

from collections import namedtuple

logger = logging.getLogger(__name__)

INPROGRESS_STATUSES = ('CREATE_IN_PROGRESS',
                       'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
                       'UPDATE_IN_PROGRESS')
COMPLETE_STATUSES = ('CREATE_COMPLETE', 'UPDATE_COMPLETE')

Status = namedtuple('Status', ['name', 'code'])
PENDING = Status('pending', 0)
SUBMITTED = Status('submitted', 1)
COMPLETE = Status('complete', 2)
SKIPPED = Status('skipped', 3)


class BlueprintContext(object):
    def __init__(self, name, class_path, namespace, requires=None,
                 parameters=None):
        self.name = name
        self.class_path = class_path
        self.namespace = namespace
        self.parameters = parameters or {}
        requires = requires or []
        self._requires = set(requires)

        self.blueprint = None
        self.status = PENDING

    def __repr__(self):
        return self.name

    @property
    def completed(self):
        return self.status == COMPLETE

    @property
    def skipped(self):
        return self.status == SKIPPED

    @property
    def submitted(self):
        return self.status.code >= SUBMITTED.code

    @property
    def requires(self):
        requires = copy.deepcopy(self._requires)
        # Auto add dependencies when parameters reference the Ouptuts of
        # another stack.
        parameters = self.parameters
        for value in parameters.values():
            if isinstance(value, basestring) and '::' in value:
                stack_name, _ = value.split('::')
            else:
                continue
            if stack_name not in requires:
                requires.add(stack_name)
        return requires

    def set_status(self, status):
        logger.debug("Setting %s state to %s.", self.name, status.name)
        self.status = status

    def complete(self):
        self.set_status(COMPLETE)

    def submit(self):
        self.set_status(SUBMITTED)

    def skip(self):
        self.set_status(SKIPPED)


class Plan(OrderedDict):
    """ Used to organize the order in which stacks will be created/updated.
    """
    def add(self, definition):
        self[definition['name']] = BlueprintContext(**definition)

    def _parse_items(self, items):
        if isinstance(items, Iterable) and not isinstance(items, basestring):
            return items
        return [items, ]

    def complete(self, items):
        items = self._parse_items(items)
        for i in items:
            self[i].complete()

    def submit(self, items):
        items = self._parse_items(items)
        for i in items:
            self[i].submit()

    def skip(self, items):
        items = self._parse_items(items)
        for i in items:
            self[i].skip()

    def list_status(self, status):
        result = OrderedDict()
        for k, record in self.items():
            if record.status == status:
                result[k] = record
        return result

    def list_completed(self):
        return self.list_status(COMPLETE)

    def list_submitted(self):
        return self.list_status(SUBMITTED)

    def list_skipped(self):
        return self.list_status(SKIPPED)

    def list_pending(self):
        """ Pending is any task that isn't COMPLETE or SKIPPED. """
        result = OrderedDict()
        for k, record in self.items():
            if record.status != COMPLETE and record.status != SKIPPED:
                result[k] = record
        return result

    @property
    def completed(self):
        if self.list_pending():
            return False
        return True
