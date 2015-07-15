import argparse
import unittest

from stacker.commands import Stacker


class TestStacker(unittest.TestCase):

    def test_stacker_build_parse_args(self):
        stacker = Stacker()
        parser = argparse.ArgumentParser(description=stacker.description)
        stacker.add_subcommands(parser)
        args = parser.parse_args(
            ['build', '-p', 'BaseDomain=mike.com', '-r', 'us-west-2', '-p',
             'AZCount=2', '-p', 'CidrBlock=10.128.0.0/16', 'stacker-test',
             'stacker/tests/fixtures/vpc-bastion-db-web.yaml']
        )
        # verify parameters
        parameters = args.parameters
        self.assertEqual(parameters['BaseDomain'], 'mike.com')
        self.assertEqual(parameters['CidrBlock'], '10.128.0.0/16')
        self.assertEqual(parameters['AZCount'], '2')
        self.assertEqual(args.region, 'us-west-2')
        self.assertEqual(args.namespace, 'stacker-test')
        self.assertFalse(args.outline)
        stacker.configure(args)
