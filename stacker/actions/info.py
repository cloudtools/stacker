from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import logging
import json
import sys

from .base import BaseAction
from .. import exceptions

logger = logging.getLogger(__name__)


class Exporter(object):
    def __init__(self, context):
        self.context = context

    def start(self):
        pass

    def start_stack(self, stack):
        pass

    def end_stack(self, stack):
        pass

    def write_output(self, key, value):
        pass

    def finish(self):
        pass


class JsonExporter(Exporter):
    def start(self):
        self.current_outputs = {}
        self.stacks = {}

    def start_stack(self, stack):
        self.current_outputs = {}

    def end_stack(self, stack):
        self.stacks[stack.name] = {
            "outputs": self.current_outputs,
            "fqn": stack.fqn
        }
        self.current_outputs = {}

    def write_output(self, key, value):
        self.current_outputs[key] = value

    def finish(self):
        json_data = json.dumps({'stacks': self.stacks}, indent=4)
        sys.stdout.write(json_data)
        sys.stdout.write('\n')
        sys.stdout.flush()


class PlainExporter(Exporter):
    def start(self):
        self.current_stack = None

    def start_stack(self, stack):
        self.current_stack = stack.name

    def end_stack(self, stack):
        self.current_stack = None

    def write_output(self, key, value):
        line = '{}.{}={}\n'.format(self.current_stack, key, value)
        sys.stdout.write(line)

    def finish(self):
        sys.stdout.flush()


class LogExporter(Exporter):
    def start(self):
        logger.info('Outputs for stacks: %s', self.context.get_fqn())

    def start_stack(self, stack):
        logger.info('%s:', stack.fqn)

    def write_output(self, key, value):
        logger.info('\t{}: {}'.format(key, value))


EXPORTER_CLASSES = {
    'json': JsonExporter,
    'log': LogExporter,
    'plain': PlainExporter
}

OUTPUT_FORMATS = list(EXPORTER_CLASSES.keys())


class Action(BaseAction):
    """Get information on CloudFormation stacks.

    Displays the outputs for the set of CloudFormation stacks.

    """

    @classmethod
    def build_exporter(cls, name):
        try:
            exporter_cls = EXPORTER_CLASSES[name]
        except KeyError:
            logger.error('Unknown output format "{}"'.format(name))
            raise

        try:
            return exporter_cls()
        except Exception:
            logger.exception('Failed to create exporter instance')
            raise

    def run(self, output_format='log', *args, **kwargs):
        if not self.context.get_stacks():
            logger.warn('WARNING: No stacks detected (error in config?)')
            return

        exporter = self.build_exporter(output_format)
        exporter.start(self.context)

        for stack in self.context.get_stacks():
            provider = self.build_provider(stack)

            try:
                provider_stack = provider.get_stack(stack.fqn)
            except exceptions.StackDoesNotExist:
                logger.info('Stack "%s" does not exist.' % (stack.fqn,))
                continue

            exporter.start_stack(stack)

            if 'Outputs' in provider_stack:
                for output in provider_stack['Outputs']:
                    exporter.write_output(output['OutputKey'],
                                          output['OutputValue'])

            exporter.end_stack(stack)

        exporter.finish()
