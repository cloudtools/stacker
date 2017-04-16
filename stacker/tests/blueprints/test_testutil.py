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


expected = """{
    "Resources": {
        "repo1Repository": {
            "Properties": {
                "RepositoryName": "repo1"
            },
            "Type": "AWS::ECR::Repository"
        },
        "repo2Repository": {
            "Properties": {
                "RepositoryName": "repo2"
            },
            "Type": "AWS::ECR::Repository"
        }
    }
}"""


class TestRepositories(BlueprintTestCase):
    def test_create_template_passes(self):
        ctx = Context({'namespace': 'test'})
        blueprint = Repositories('test_repo', ctx)
        blueprint.resolve_variables([
            Variable('Repositories', ["repo1", "repo2"])
        ])
        blueprint.create_template()
        self.assertRenderedBlueprint(blueprint, dump=False, expected=expected)

    def test_create_template_fails(self):
        ctx = Context({'namespace': 'test'})
        blueprint = Repositories('test_repo', ctx)
        blueprint.resolve_variables([
            Variable('Repositories', ["repo1", "repo2", "repo3"])
        ])
        blueprint.create_template()
        with self.assertRaises(AssertionError):
            self.assertRenderedBlueprint(blueprint, dump=False,
                                         expected=expected)


if __name__ == '__main__':
    unittest.main()
