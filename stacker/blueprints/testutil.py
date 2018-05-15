import difflib
import json
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
