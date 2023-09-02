from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import json
import unittest

from mock import Mock, patch
from six import StringIO

from stacker.context import Context, Config
from stacker.actions.info import (
    JsonExporter,
    PlainExporter
)


def stack_mock(name, **kwargs):
    m = Mock(**kwargs)
    m.name = name
    return m


class TestExporters(unittest.TestCase):
    def setUp(self):
        self.context = Context(config=Config({"namespace": "namespace"}))
        self.stacks = [
            stack_mock(name='vpc', fqn='namespace-test-1'),
            stack_mock(name='bucket', fqn='namespace-test-2'),
            stack_mock(name='role', fqn='namespace-test-3')
        ]
        self.outputs = {
            'vpc': {
                'VpcId': 'vpc-123456',
                'VpcName': 'dev'
            },
            'bucket': {
                'BucketName': 'my-bucket'
            },
            'role': {
                'RoleName': 'my-role',
                'RoleArn': 'arn:::'
            }
        }

    def run_export(self, exporter):
        exporter.start()

        for stack in self.stacks:
            exporter.start_stack(stack)
            for key, value in self.outputs[stack.name].items():
                exporter.write_output(key, value)
            exporter.end_stack(stack)

        exporter.finish()

    def test_json(self):
        exporter = JsonExporter(self.context)
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.run_export(exporter)

        json_data = json.loads(fake_out.getvalue().strip())
        self.assertEqual(
            json_data,
            {
                u'stacks': {
                    u'vpc': {
                        u'fqn': u'namespace-vpc',
                        u'outputs': self.outputs['vpc']
                    },
                    'bucket': {
                        u'fqn': u'namespace-bucket',
                        u'outputs': self.outputs['bucket']
                    },
                    u'role': {
                        u'fqn': u'namespace-role',
                        u'outputs': self.outputs['role']
                    }
                }
            })

    def test_plain(self):
        exporter = PlainExporter(self.context)
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.run_export(exporter)

        lines = fake_out.getvalue().strip().splitlines()

        for stack_name, outputs in self.outputs.items():
            for key, value in outputs.items():
                line = '{}.{}={}'.format(stack_name, key, value)
                self.assertIn(line, lines)
