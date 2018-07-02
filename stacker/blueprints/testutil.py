from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import difflib
import json
import unittest
import os.path
from glob import glob

from stacker.config import parse as parse_config
from stacker.context import Context
from stacker.util import load_object_from_string
from stacker.variables import Variable


def diff(a, b):
    """A human readable differ."""
    return '\n'.join(
        list(
            difflib.Differ().compare(
                a.splitlines(),
                b.splitlines()
            )
        )
    )


class BlueprintTestCase(unittest.TestCase):
    OUTPUT_PATH = "tests/fixtures/blueprints"

    def assertRenderedBlueprint(self, blueprint):  # noqa: N802
        expected_output = "%s/%s.json" % (self.OUTPUT_PATH, blueprint.name)

        rendered_dict = blueprint.template.to_dict()
        rendered_text = json.dumps(rendered_dict, indent=4, sort_keys=True)

        with open(expected_output + "-result", "w") as fd:
            fd.write(rendered_text)

        with open(expected_output) as fd:
            expected_dict = json.loads(fd.read())
            expected_text = json.dumps(expected_dict, indent=4, sort_keys=True)

        self.assertEquals(rendered_dict, expected_dict,
                          diff(rendered_text, expected_text))


class YamlDirTestGenerator(object):
    """Generate blueprint tests from yaml config files.

    This class creates blueprint tests from yaml files with a syntax similar to
    stackers' configuration syntax. For example,

       ---
       namespace: test
       stacks:
         - name: test_sample
           class_path: stacker_blueprints.test.Sample
           variables:
             var1: value1

    will create a test for the specified blueprint, passing that variable as
    part of the test.

    The test will generate a .json file for this blueprint, and compare it with
    the stored result.


    By default, the generator looks for files named 'test_*.yaml' in its same
    directory. In order to use it, subclass it in a directory containing such
    tests, and name the class with a pattern that will include it in nosetests'
    tests (for example, TestGenerator).

    The subclass may override some properties:

    @property base_class: by default, the generated tests are subclasses of
    stacker.blueprints.testutil.BlueprintTestCase. In order to change this,
    set this property to the desired base class.

    @property yaml_dirs: by default, the directory where the generator is
    subclassed is searched for test files. Override this array for specifying
    more directories. These must be relative to the directory in which the
    subclass lives in. Globs may be used.
        Default: [ '.' ]. Example override: [ '.', 'tests/*/' ]

    @property yaml_filename: by default, the generator looks for files named
    'test_*.yaml'. Use this to change this pattern. Globs may be used.


    There's an example of this use in the tests/ subdir of stacker_blueprints.

    """

    def __init__(self):
        self.classdir = os.path.relpath(
            self.__class__.__module__.replace('.', '/'))
        if not os.path.isdir(self.classdir):
            self.classdir = os.path.dirname(self.classdir)

    # These properties can be overriden from the test generator subclass.
    @property
    def base_class(self):
        return BlueprintTestCase

    @property
    def yaml_dirs(self):
        return ['.']

    @property
    def yaml_filename(self):
        return 'test_*.yaml'

    def test_generator(self):
        # Search for tests in given paths
        configs = []
        for d in self.yaml_dirs:
            configs.extend(
                glob('%s/%s/%s' % (self.classdir, d, self.yaml_filename)))

        class ConfigTest(self.base_class):
            def __init__(self, config, stack, filepath):
                self.config = config
                self.stack = stack
                self.description = "%s (%s)" % (stack.name, filepath)

            def __call__(self):
                # Use the context property of the baseclass, if present.
                # If not, default to a basic context.
                try:
                    ctx = self.context
                except AttributeError:
                    ctx = Context(config=self.config,
                                  environment={'environment': 'test'})

                configvars = self.stack.variables or {}
                variables = [Variable(k, v) for k, v in configvars.iteritems()]

                blueprint_class = load_object_from_string(
                    self.stack.class_path)
                blueprint = blueprint_class(self.stack.name, ctx)
                blueprint.resolve_variables(variables or [])
                blueprint.setup_parameters()
                blueprint.create_template()
                self.assertRenderedBlueprint(blueprint)

            def assertEquals(self, a, b, msg):  # noqa: N802
                assert a == b, msg

        for f in configs:
            with open(f) as test:
                config = parse_config(test.read())
                config.validate()

                for stack in config.stacks:
                    # Nosetests supports "test generators", which allows us to
                    # yield a callable object which will be wrapped as a test
                    # case.
                    #
                    # http://nose.readthedocs.io/en/latest/writing_tests.html#test-generators
                    yield ConfigTest(config, stack, filepath=f)
