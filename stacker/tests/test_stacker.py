from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from stacker.commands import Stacker
from stacker.exceptions import InvalidConfig


class TestStacker(unittest.TestCase):

    def test_stacker_build_parse_args(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ["build",
             "-r", "us-west-2",
             "-e", "namespace=test.override",
             "stacker/tests/fixtures/basic.env",
             "stacker/tests/fixtures/vpc-bastion-db-web.yaml"]
        )
        self.assertEqual(args.region, "us-west-2")
        self.assertFalse(args.outline)
        # verify namespace was modified
        self.assertEqual(args.environment["namespace"], "test.override")

    def test_stacker_build_parse_args_region_from_env(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ["build",
             "-e", "namespace=test.override",
             "stacker/tests/fixtures/basic.env",
             "stacker/tests/fixtures/vpc-bastion-db-web.yaml"]
        )
        self.assertEqual(args.region, None)

    def test_stacker_build_context_passed_to_blueprint(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ["build",
             "-r", "us-west-2",
             "stacker/tests/fixtures/basic.env",
             "stacker/tests/fixtures/vpc-bastion-db-web.yaml"]
        )
        stacker.configure(args)
        stacks_dict = args.context.get_stacks_dict()
        blueprint = stacks_dict[args.context.get_fqn("bastion")].blueprint
        self.assertTrue(hasattr(blueprint, "context"))
        blueprint.render_template()
        # verify that the bastion blueprint only contains blueprint variables,
        # not BaseDomain, AZCount or CidrBlock. Any variables that get passed
        # in from the command line shouldn't be resovled at the blueprint level
        self.assertNotIn("BaseDomain", blueprint.template.parameters)
        self.assertNotIn("AZCount", blueprint.template.parameters)
        self.assertNotIn("CidrBlock", blueprint.template.parameters)

    def test_stacker_blueprint_property_access_does_not_reset_blueprint(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ["build",
             "-r", "us-west-2",
             "stacker/tests/fixtures/basic.env",
             "stacker/tests/fixtures/vpc-bastion-db-web.yaml"]
        )
        stacker.configure(args)
        stacks_dict = args.context.get_stacks_dict()
        bastion_stack = stacks_dict[args.context.get_fqn("bastion")]
        bastion_stack.blueprint.render_template()
        self.assertIn("DefaultSG", bastion_stack.blueprint.template.parameters)

    def test_stacker_build_context_stack_names_specified(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ["build",
             "-r", "us-west-2",
             "stacker/tests/fixtures/basic.env",
             "stacker/tests/fixtures/vpc-bastion-db-web.yaml",
             "--stacks", "vpc",
             "--stacks", "bastion"]
        )
        stacker.configure(args)
        stacks = args.context.get_stacks()
        self.assertEqual(len(stacks), 2)

    def test_stacker_build_fail_when_parameters_in_stack_def(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ["build",
             "-r", "us-west-2",
             "stacker/tests/fixtures/basic.env",
             "stacker/tests/fixtures/vpc-bastion-db-web-pre-1.0.yaml"]
        )
        with self.assertRaises(InvalidConfig):
            stacker.configure(args)


if __name__ == '__main__':
    unittest.main()
