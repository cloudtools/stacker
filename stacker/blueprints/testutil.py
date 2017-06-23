import difflib
import unittest


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

    def assertEqualsDiff(self, a, b):  # noqa: N802
        self.assertEquals(a, b, diff(a, b))

    def assertRenderedBlueprint(self, blueprint):  # noqa: N802
        expected_output = "%s/%s.json" % (self.OUTPUT_PATH, blueprint.name)
        rendered = blueprint.template.to_json()

        with open(expected_output + "-result", "w") as fd:
            fd.write(rendered)

        with open(expected_output) as fd:
            expected = fd.read()

        self.assertEqualsDiff(rendered, expected)
