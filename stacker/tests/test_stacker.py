import argparse
import unittest

from stacker.commands import Stacker


class TestStacker(unittest.TestCase):

    def test_stacker_build_parse_args(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ['build', '-p', 'BaseDomain=mike.com', '-r', 'us-west-2', '-p',
             'AZCount=2', '-p', 'CidrBlock=10.128.0.0/16',
             '-e', 'namespace=test.override',
             'stacker/tests/fixtures/basic.env',
             'stacker/tests/fixtures/vpc-bastion-db-web.yaml']
        )
        # verify parameters
        parameters = args.parameters
        self.assertEqual(parameters['BaseDomain'], 'mike.com')
        self.assertEqual(parameters['CidrBlock'], '10.128.0.0/16')
        self.assertEqual(parameters['AZCount'], '2')
        self.assertEqual(args.region, 'us-west-2')
        self.assertFalse(args.outline)
        # verify namespace was modified
        self.assertEqual(args.environment['namespace'], 'test.override')

    def test_stacker_build_context_passed_to_blueprint(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ['build', '-p', 'BaseDomain=mike.com', '-r', 'us-west-2', '-p',
             'AZCount=2', '-p', 'CidrBlock=10.128.0.0/16',
             'stacker/tests/fixtures/basic.env',
             'stacker/tests/fixtures/vpc-bastion-db-web.yaml']
        )
        stacker.configure(args)
        stacks_dict = args.context.get_stacks_dict()
        blueprint = stacks_dict[args.context.get_fqn('bastion')].blueprint
        self.assertTrue(hasattr(blueprint, 'context'))
        blueprint.create_template()
        blueprint.setup_parameters()
        # verify that the bastion blueprint only contains blueprint parameters,
        # not BaseDomain, AZCount or CidrBlock. Any parameters that get passed
        # in from the command line shouldn't be resovled at the blueprint level
        self.assertNotIn('BaseDomain', blueprint.parameters)
        self.assertNotIn('AZCount', blueprint.parameters)
        self.assertNotIn('CidrBlock', blueprint.parameters)

    def test_stacker_blueprint_property_access_does_not_reset_blueprint(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ['build', '-p', 'BaseDomain=mike.com', '-r', 'us-west-2', '-p',
             'AZCount=2', '-p', 'CidrBlock=10.128.0.0/16',
             'stacker/tests/fixtures/basic.env',
             'stacker/tests/fixtures/vpc-bastion-db-web.yaml']
        )
        stacker.configure(args)
        stacks_dict = args.context.get_stacks_dict()
        bastion_stack = stacks_dict[args.context.get_fqn('bastion')]
        bastion_stack.blueprint.create_template()
        bastion_stack.blueprint.setup_parameters()
        self.assertIn('DefaultSG', bastion_stack.blueprint.parameters)

    def test_stacker_build_context_stack_names_specified(self):
        stacker = Stacker()
        args = stacker.parse_args(
            ['build', '-p', 'BaseDomain=mike.com', '-r', 'us-west-2', '-p',
             'AZCount=2', '-p', 'CidrBlock=10.128.0.0/16',
             'stacker/tests/fixtures/basic.env',
             'stacker/tests/fixtures/vpc-bastion-db-web.yaml', '--stacks',
             'vpc', '--stacks', 'bastion']
        )
        stacker.configure(args)
        stacks = args.context.get_stacks()
        self.assertEqual(len(stacks), 2)
