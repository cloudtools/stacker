import unittest

from ..context import Context


class TestContext(unittest.TestCase):

    def setUp(self):
        self.config = {'stacks': [{'name': 'stack1'}, {'name': 'stack2'}]}

    def test_context_optional_keys_defaults(self):
        context = Context('namespace')
        for key in context._optional_keys:
            self.assertTrue(hasattr(context, key))

    def test_context_optional_keys_set(self):
        context = Context(
            'namespace',
            environment={},
            stack_names=['stack'],
            mappings={},
            config={},
        )
        for key in ['environment', 'mappings', 'config']:
            self.assertEqual(getattr(context, key), {})
        self.assertEqual(context.stack_names, ['stack'])

    def test_context_get_stacks_specific_stacks(self):
        context = Context('namespace', config=self.config, stack_names=['stack2'])
        self.assertEqual(len(context.get_stacks()), 1)

    def test_context_get_stacks(self):
        context = Context('namespace', config=self.config)
        self.assertEqual(len(context.get_stacks()), 2)

    def test_context_get_fqn(self):
        context = Context('namespace')
        fqn = context.get_fqn()
        self.assertEqual(fqn, 'namespace')

    def test_context_get_fqn_replace_dot(self):
        context = Context('my.namespace')
        fqn = context.get_fqn()
        self.assertEqual(fqn, 'my-namespace')

    def test_context_get_fqn_stack_name(self):
        context = Context('namespace')
        fqn = context.get_fqn('stack1')
        self.assertEqual(fqn, 'namespace-stack1')
