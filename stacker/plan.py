import logging

logger = logging.getLogger(__name__)

import copy
from collections import OrderedDict, Iterable

INPROGRESS_STATUSES = ('CREATE_IN_PROGRESS',
                       'UPDATE_COMPLETE_CLEANUP_IN_PROGRESS',
                       'UPDATE_IN_PROGRESS')
COMPLETE_STATUSES = ('CREATE_COMPLETE', 'UPDATE_COMPLETE')

STATUS_SUBMITTED = 1
STATUS_COMPLETE = 2


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
        self.status = None

    def __repr__(self):
        return self.name

    @property
    def completed(self):
        return self.status == STATUS_COMPLETE

    @property
    def submitted(self):
        return self.status >= STATUS_SUBMITTED

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

    def complete(self):
        logger.debug("Setting %s state to complete.", self.name)
        self.status = STATUS_COMPLETE

    def submit(self):
        logger.debug("Setting %s state to submitted.", self.name)
        self.status = STATUS_SUBMITTED


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

    def list_completed(self):
        result = OrderedDict()
        for k, record in self.items():
            if record.status == STATUS_COMPLETE:
                result[k] = record
        return result

    def list_pending(self):
        result = OrderedDict()
        for k, record in self.items():
            if record.status != STATUS_COMPLETE:
                result[k] = record
        return result

    def list_submitted(self):
        result = OrderedDict()
        for k, record in self.items():
            if record.status == STATUS_SUBMITTED:
                result[k] = record
        return result

    @property
    def completed(self):
        if self.list_pending():
            return False
        return True
