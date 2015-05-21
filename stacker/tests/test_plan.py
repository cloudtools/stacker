import unittest

import mock

from stacker.plan import Step, Plan
from stacker.stack import Stack

from .factories import generate_definition

count = 0


class TestStep(unittest.TestCase):

    def setUp(self):
        stack = Stack(generate_definition('vpc', 1))
        self.step = Step(
            stack=stack,
            index=0,
            run_func=lambda x, y: (x, y),
            completion_func=lambda y: True,
        )

    def test_status(self):
        self.assertFalse(self.step.submitted)
        self.assertFalse(self.step.completed)
        self.step.submit()
        self.assertTrue(self.step.submitted)
        self.assertFalse(self.step.completed)
        self.step.complete()
        self.assertTrue(self.step.submitted)
        self.assertTrue(self.step.completed)


class TestPlan(unittest.TestCase):

    def setUp(self):
        self.count = 0
        self.plan = Plan(provider=mock.MagicMock(), sleep_time=0)
        for i in range(4):
            stack = Stack(generate_definition('vpc', i))
            self.plan.add(
                stack=stack,
                run_func=self._run_func,
                completion_func=self._completion_func,
            )

    def _run_func(self, results, stack):
        self.count += 1
        if not self.count % 2:
            return True
        return False

    def _completion_func(self, stack):
        return self.count

    def test_execute_plan(self):
        results = self.plan.execute()
        self.assertEqual(self.count, 8)
        self.assertEqual(results[self.plan.keys()[0]], 2)
        self.assertEqual(results[self.plan.keys()[-1]], 8)
