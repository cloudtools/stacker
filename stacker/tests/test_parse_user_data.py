import unittest

import yaml

from ..tokenize_userdata import cf_tokenize


class TestCfTokenize(unittest.TestCase):
    def test_tokenize(self):
        user_data = [
            "field0",
            "Ref(\"SshKey\")",
            "field1",
            "Fn::GetAtt(\"Blah\", \"Woot\")"
        ]
        ud = yaml.dump(user_data)
        parts = cf_tokenize(ud)
        self.assertIsInstance(parts[1], dict)
        self.assertIsInstance(parts[3], dict)
        self.assertEqual(parts[1]["Ref"], "SshKey")
        self.assertEqual(parts[3]["Fn::GetAtt"], ["Blah", "Woot"])
        self.assertEqual(len(parts), 5)
