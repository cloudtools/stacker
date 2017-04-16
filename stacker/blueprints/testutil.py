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
    def assertEqualsDiff(self, a, b):  # noqa: N802
        self.assertEquals(a, b, diff(a, b))

    def assertRenderedBlueprint(self, blueprint, dump=True,  # noqa: N802
                                expected=None):
        expected_output = "tests/fixtures/blueprints/%s.json" % blueprint.name
        rendered = blueprint.template.to_json()

        if dump:
            with open(expected_output + "-result", "w") as fd:
                fd.write(rendered)

        if not expected:
            with open(expected_output) as fd:
                expected = fd.read()

        self.assertEqualsDiff(rendered, expected)
