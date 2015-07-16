import unittest

import mock

from stacker.plan import COMPLETE, PENDING, SKIPPED, SUBMITTED, Step, Plan
from stacker.stack import Stack

from .factories import generate_definition

count = 0


class TestStep(unittest.TestCase):

    def setUp(self):
        stack = Stack(
            definition=generate_definition('vpc', 1),
            context=mock.MagicMock(),
        )
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
        self.plan = Plan(details='Test', provider=mock.MagicMock(), sleep_time=0)
        for i in range(5):
            stack = Stack(
                definition=generate_definition('vpc', i),
                context=mock.MagicMock(),
            )
            self.plan.add(
                stack=stack,
                run_func=self._run_func,
                completion_func=self._completion_func,
            )

    def _run_func(self, results, stack, **kwargs):
        self.assertIn('status', kwargs, 'Step "status" should be passed to all run_funcs')
        self.count += 1
        if not self.count % 2:
            return COMPLETE
        elif self.count == 9:
            return SKIPPED
        return SUBMITTED

    def _completion_func(self, stack):
        return self.count

    def test_execute_plan(self):
        results = self.plan.execute()
        self.assertEqual(self.count, 9)
        self.assertEqual(results[self.plan.keys()[0]], 2)
        self.assertEqual(results[self.plan.keys()[-2]], 8)
        self.assertEqual(len(self.plan.list_skipped()), 1)

    def test_step_must_return_status(self):
        plan = Plan(details='Test', provider=mock.MagicMock(), sleep_time=0)
        stack = Stack(definition=generate_definition('vpc', 1), context=mock.MagicMock())
        plan.add(
            stack=stack,
            run_func=lambda x, y,
            **kwargs: (x, y),
            completion_func=lambda x: True,
        )
        with self.assertRaises(ValueError):
            plan.execute()
