from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from stacker.context import Context, get_fqn
from stacker.config import load, Config
from stacker.util import handle_hooks


class TestContext(unittest.TestCase):

    def setUp(self):
        self.config = Config({
            "namespace": "namespace",
            "stacks": [
                {"name": "stack1"}, {"name": "stack2"}]})

    def test_context_optional_keys_set(self):
        context = Context(
            config=Config({}),
            stack_names=["stack"],
        )
        self.assertEqual(context.mappings, {})
        self.assertEqual(context.stack_names, ["stack"])

    def test_context_get_stacks(self):
        context = Context(config=self.config)
        self.assertEqual(len(context.get_stacks()), 2)

    def test_context_get_stacks_dict_use_fqn(self):
        context = Context(config=self.config)
        stacks_dict = context.get_stacks_dict()
        stack_names = sorted(stacks_dict.keys())
        self.assertEqual(stack_names[0], "namespace-stack1")
        self.assertEqual(stack_names[1], "namespace-stack2")

    def test_context_get_fqn(self):
        context = Context(config=self.config)
        fqn = context.get_fqn()
        self.assertEqual(fqn, "namespace")

    def test_context_get_fqn_replace_dot(self):
        context = Context(config=Config({"namespace": "my.namespace"}))
        fqn = context.get_fqn()
        self.assertEqual(fqn, "my-namespace")

    def test_context_get_fqn_empty_namespace(self):
        context = Context(config=Config({"namespace": ""}))
        fqn = context.get_fqn("vpc")
        self.assertEqual(fqn, "vpc")
        self.assertEqual(context.tags, {})

    def test_context_namespace(self):
        context = Context(config=Config({"namespace": "namespace"}))
        self.assertEqual(context.namespace, "namespace")

    def test_context_get_fqn_stack_name(self):
        context = Context(config=self.config)
        fqn = context.get_fqn("stack1")
        self.assertEqual(fqn, "namespace-stack1")

    def test_context_default_bucket_name(self):
        context = Context(config=Config({"namespace": "test"}))
        self.assertEqual(context.bucket_name, "stacker-test")

    def test_context_bucket_name_is_overriden_but_is_none(self):
        config = Config({"namespace": "test", "stacker_bucket": ""})
        context = Context(config=config)
        self.assertEqual(context.bucket_name, None)

        config = Config({"namespace": "test", "stacker_bucket": None})
        context = Context(config=config)
        self.assertEqual(context.bucket_name, "stacker-test")

    def test_context_bucket_name_is_overriden(self):
        config = Config({"namespace": "test", "stacker_bucket": "bucket123"})
        context = Context(config=config)
        self.assertEqual(context.bucket_name, "bucket123")

    def test_context_default_bucket_no_namespace(self):
        context = Context(config=Config({"namespace": ""}))
        self.assertEqual(context.bucket_name, None)

        context = Context(config=Config({"namespace": None}))
        self.assertEqual(context.bucket_name, None)

        context = Context(
            config=Config({"namespace": None, "stacker_bucket": ""}))
        self.assertEqual(context.bucket_name, None)

    def test_context_namespace_delimiter_is_overriden_and_not_none(self):
        config = Config({"namespace": "namespace", "namespace_delimiter": "_"})
        context = Context(config=config)
        fqn = context.get_fqn("stack1")
        self.assertEqual(fqn, "namespace_stack1")

    def test_context_namespace_delimiter_is_overriden_and_is_empty(self):
        config = Config({"namespace": "namespace", "namespace_delimiter": ""})
        context = Context(config=config)
        fqn = context.get_fqn("stack1")
        self.assertEqual(fqn, "namespacestack1")

    def test_context_tags_with_empty_map(self):
        config = Config({"namespace": "test", "tags": {}})
        context = Context(config=config)
        self.assertEqual(context.tags, {})

    def test_context_no_tags_specified(self):
        config = Config({"namespace": "test"})
        context = Context(config=config)
        self.assertEqual(context.tags, {"stacker_namespace": "test"})

    def test_hook_with_sys_path(self):
        config = Config({
            "namespace": "test",
            "sys_path": "stacker/tests",
            "pre_build": [
                {
                    "data_key": "myHook",
                    "path": "fixtures.mock_hooks.mock_hook",
                    "required": True,
                    "args": {
                        "value": "mockResult"}}]})
        load(config)
        context = Context(config=config)
        stage = "pre_build"
        handle_hooks(stage, context.config[stage], "mock-region-1", context)
        self.assertEqual("mockResult", context.hook_data["myHook"]["result"])


class TestFunctions(unittest.TestCase):
    """ Test the module level functions """
    def test_get_fqn_redundant_base(self):
        base = "woot"
        name = "woot-blah"
        self.assertEqual(get_fqn(base, '-', name), name)
        self.assertEqual(get_fqn(base, '', name), name)
        self.assertEqual(get_fqn(base, '_', name), "woot_woot-blah")

    def test_get_fqn_only_base(self):
        base = "woot"
        self.assertEqual(get_fqn(base, '-'), base)
        self.assertEqual(get_fqn(base, ''), base)
        self.assertEqual(get_fqn(base, '_'), base)

    def test_get_fqn_full(self):
        base = "woot"
        name = "blah"
        self.assertEqual(get_fqn(base, '-', name), "%s-%s" % (base, name))
        self.assertEqual(get_fqn(base, '', name), "%s%s" % (base, name))
        self.assertEqual(get_fqn(base, '_', name), "%s_%s" % (base, name))


if __name__ == '__main__':
    unittest.main()
