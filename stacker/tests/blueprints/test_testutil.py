from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
import unittest

from troposphere import ecr

from ...blueprints.testutil import BlueprintTestCase
from ...blueprints.base import Blueprint
from ...context import Context
from ...variables import Variable


class Repositories(Blueprint):
    """ Simple blueprint to test our test cases. """
    VARIABLES = {
        "Repositories": {
            "type": list,
            "description": "A list of repository names to create."
        }
    }

    def create_template(self):
        t = self.template
        variables = self.get_variables()

        for repo in variables["Repositories"]:
            t.add_resource(
                ecr.Repository(
                    "%sRepository" % repo,
                    RepositoryName=repo,
                )
            )


class TestRepositories(BlueprintTestCase):
    def test_create_template_passes(self):
        ctx = Context({'namespace': 'test'})
        blueprint = Repositories('test_repo', ctx)
        blueprint.resolve_variables([
            Variable('Repositories', ["repo1", "repo2"])
        ])
        blueprint.create_template()
        self.assertRenderedBlueprint(blueprint)

    def test_create_template_fails(self):
        ctx = Context({'namespace': 'test'})
        blueprint = Repositories('test_repo', ctx)
        blueprint.resolve_variables([
            Variable('Repositories', ["repo1", "repo2", "repo3"])
        ])
        blueprint.create_template()
        with self.assertRaises(AssertionError):
            self.assertRenderedBlueprint(blueprint)


if __name__ == '__main__':
    unittest.main()
