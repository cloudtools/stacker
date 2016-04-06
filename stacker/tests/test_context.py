import unittest

from ..context import Context, get_fqn
from ..exceptions import MissingEnvironment


class TestContext(unittest.TestCase):

    def setUp(self):
        self.environment = {'namespace': 'namespace'}
        self.config = {'stacks': [{'name': 'stack1'}, {'name': 'stack2'}]}

    def test_context_environment_namespace_required(self):
        with self.assertRaises(TypeError):
            Context()

        with self.assertRaises(MissingEnvironment):
            Context({'value': 'random'})

        context = Context({'namespace': 'test'})
        self.assertEqual(context.namespace, 'test')

    def test_context_optional_keys_set(self):
        context = Context(
            environment=self.environment,
            stack_names=['stack'],
            mappings={},
            config={},
        )
        for key in ['mappings', 'config']:
            self.assertEqual(getattr(context, key), {})
        self.assertEqual(context.stack_names, ['stack'])

    def test_context_get_stacks_specific_stacks(self):
        context = Context(
            environment=self.environment,
            config=self.config,
            stack_names=['stack2'],
        )
        self.assertEqual(len(context.get_stacks()), 1)

    def test_context_get_stacks(self):
        context = Context(self.environment, config=self.config)
        self.assertEqual(len(context.get_stacks()), 2)

    def test_context_get_stacks_dict_use_fqn(self):
        context = Context(self.environment, config=self.config)
        stacks_dict = context.get_stacks_dict()
        stack_names = sorted(stacks_dict.keys())
        self.assertEqual(stack_names[0], 'namespace-stack1')
        self.assertEqual(stack_names[1], 'namespace-stack2')

    def test_context_get_fqn(self):
        context = Context(self.environment)
        fqn = context.get_fqn()
        self.assertEqual(fqn, 'namespace')

    def test_context_get_fqn_replace_dot(self):
        context = Context({'namespace': 'my.namespace'})
        fqn = context.get_fqn()
        self.assertEqual(fqn, 'my-namespace')

    def test_context_get_fqn_stack_name(self):
        context = Context(self.environment)
        fqn = context.get_fqn('stack1')
        self.assertEqual(fqn, 'namespace-stack1')

    def test_context_default_bucket_name(self):
        context = Context({'namespace': 'test'})
        context.load_config("""mappings:""")
        self.assertEqual(context.bucket_name, 'stacker-test')

    def test_context_bucket_name_is_overriden_but_is_none(self):
        context = Context({'namespace': 'test'})
        context.load_config("""stacker_bucket:""")
        self.assertEqual(context.bucket_name, 'stacker-test')

    def test_context_bucket_name_is_overriden(self):
        context = Context({'namespace': 'test'})
        context.load_config("""stacker_bucket: bucket123""")
        self.assertEqual(context.bucket_name, 'bucket123')


class TestFunctions(unittest.TestCase):
    """ Test the module level functions """
    def test_get_fqn_redundant_base(self):
        base = "woot"
        name = "woot-blah"
        self.assertEqual(get_fqn(base, name), name)

    def test_get_fqn_only_base(self):
        base = "woot"
        self.assertEqual(get_fqn(base), base)

    def test_get_fqn_full(self):
        base = "woot"
        name = "blah"
        self.assertEqual(get_fqn(base, name), "%s-%s" % (base, name))
