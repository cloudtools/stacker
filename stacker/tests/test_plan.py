import unittest
import mock

from stacker.exceptions import ImproperlyConfigured
from stacker.plan import COMPLETE, SKIPPED, SUBMITTED, Step, Plan
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
        plan = Plan(details='Test', provider=mock.MagicMock(), sleep_time=0)
        _skip_func = mock.MagicMock()
        previous_stack = None
        for i in range(5):
            overrides = {}
            if previous_stack:
                overrides['requires'] = [previous_stack.name]
            stack = Stack(
                definition=generate_definition('vpc', i, **overrides),
                context=mock.MagicMock(),
            )
            previous_stack = stack
            plan.add(
                stack=stack,
                run_func=self._run_func,
                completion_func=self._completion_func,
                skip_func=_skip_func,
                requires=stack.requires,
            )
        results = plan.execute()
        self.assertEqual(self.count, 9)
        self.assertEqual(results[plan.keys()[0]], 2)
        self.assertEqual(results[plan.keys()[-2]], 8)
        self.assertEqual(len(plan.list_skipped()), 1)
        self.assertEqual(len(plan.list_skipped()), _skip_func.call_count)

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

    def test_execute_plan_ensure_parallel_builds(self):

        results = {}

        def _test_stack_name(stack):
            # use a test_stack_name since the plan execution treats the stack
            # name in the results as a completed stack (either skipped or complete)
            return '_test_%s' % (stack.name,)

        def _run_func(results, stack, *args, **kwargs):
            test_stack_name = _test_stack_name(stack)
            if test_stack_name not in results:
                results[test_stack_name] = 0

            if results[test_stack_name] and not results[test_stack_name] % 2:
                return COMPLETE
            else:
                results[test_stack_name] += 1
                return SUBMITTED

        vpc_stack = Stack(definition=generate_definition('vpc', 1), context=mock.MagicMock())
        web_stack = Stack(
            definition=generate_definition('web', 2, requires=[vpc_stack.name]),
            context=mock.MagicMock(),
        )
        db_stack = Stack(
            definition=generate_definition('db', 3, requires=[vpc_stack.name]),
            context=mock.MagicMock(),
        )

        def _wait_func(sleep_time):
            vpc_stack_test_name = _test_stack_name(vpc_stack)
            web_stack_test_name = _test_stack_name(web_stack)
            db_stack_test_name = _test_stack_name(db_stack)
            if web_stack_test_name in results:
                # verify the vpc stack has completed
                self.assertEqual(results[vpc_stack_test_name], 2)
                self.assertIn(vpc_stack.name, results)
                if db_stack_test_name not in results:
                    # verify that this is the first pass at building the
                    # web_stack, the next loop should trigger running the
                    # db_stack.
                    self.assertEqual(results[web_stack_test_name], 1)
                elif results[db_stack_test_name] == 1:
                    # verify that both the web_stack and db_stack are in
                    # progress at the same time
                    self.assertEqual(results[web_stack_test_name], 1)
                    self.assertEqual(results[db_stack_test_name], 1)

        plan = Plan(details='Test', provider=mock.MagicMock(), sleep_time=0, wait_func=_wait_func)
        for stack in [vpc_stack, web_stack, db_stack]:
            plan.add(
                stack=stack,
                run_func=_run_func,
                requires=stack.requires,
            )

        plan.execute(results)

    def test_plan_wait_func_must_be_function(self):
        with self.assertRaises(ImproperlyConfigured):
            Plan(details='Test', provider=mock.MagicMock(), wait_func='invalid')
