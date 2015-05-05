import unittest

from stacker.plan import BlueprintContext, Plan


def generate_definition(base_name, _id):
    return {
        "name": "%s.%d" % (base_name, _id),
        "class_path": "stacker.blueprints.%s.%s" % (base_name,
                                                    base_name.upper()),
        "namespace": "example-com",
        "parameters": {
            "ExternalParameter": "fakeStack2::FakeParameter",
            "InstanceType": "m3.medium",
            "AZCount": 2,
            },
        "requires": ["fakeStack"]
    }


class TestBlueprintContext(unittest.TestCase):
    def setUp(self):
        self.context = BlueprintContext(**generate_definition('vpc', 1))

    def test_status(self):
        self.assertFalse(self.context.submitted)
        self.assertFalse(self.context.completed)
        self.context.submit()
        self.assertTrue(self.context.submitted)
        self.assertFalse(self.context.completed)
        self.context.complete()
        self.assertTrue(self.context.submitted)
        self.assertTrue(self.context.completed)

    def test_requires(self):
        self.assertIn('fakeStack', self.context.requires)
        self.assertIn('fakeStack2', self.context.requires)


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.plan = Plan()
        for i in range(4):
            self.plan.add(generate_definition('vpc', i))

    def test_add(self):
        first_id = 'vpc.1'
        self.assertIn(first_id, self.plan)
        self.assertIsInstance(self.plan[first_id], BlueprintContext)

    def test_status(self):
        self.assertEqual(len(self.plan.list_submitted()), 0)
        self.assertEqual(len(self.plan.list_completed()), 0)
        self.assertEqual(len(self.plan.list_pending()), 4)
        self.plan.submit('vpc.1')
        self.assertEqual(len(self.plan.list_submitted()), 1)
        self.assertEqual(len(self.plan.list_completed()), 0)
        self.assertEqual(len(self.plan.list_pending()), 4)
        self.plan.complete('vpc.1')
        self.assertEqual(len(self.plan.list_submitted()), 0)
        self.assertEqual(len(self.plan.list_completed()), 1)
        self.assertEqual(len(self.plan.list_pending()), 3)
        self.assertFalse(self.plan.completed)
        for i in range(4):
            self.plan.complete("vpc.%d" % i)
        self.assertTrue(self.plan.completed)
