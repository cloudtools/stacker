import unittest
import mock

from stacker.context import Context
from stacker.exceptions import ImproperlyConfigured
from stacker.plan import COMPLETE, SKIPPED, SUBMITTED, Step, Plan
from stacker.stack import Stack

from .factories import generate_definition

count = 0


class TestStep(unittest.TestCase):

    def setUp(self):
        self.context = Context({'namespace': 'namespace'})
        stack = Stack(
            definition=generate_definition('vpc', 1),
            context=self.context,
        )
        self.step = Step(
            stack=stack,
            run_func=lambda x, y: (x, y),
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
        self.environment = {'namespace': 'namespace'}
        self.context = Context(self.environment)

    def _run_func(self, stack, **kwargs):
        self.count += 1
        if not self.count % 2:
            return COMPLETE
        elif self.count == 9:
            return SKIPPED
        return SUBMITTED

    def test_execute_plan(self):
        plan = Plan(description='Test', sleep_time=0)
        previous_stack = None
        for i in range(5):
            overrides = {}
            if previous_stack:
                overrides['requires'] = [previous_stack.fqn]
            stack = Stack(
                definition=generate_definition('vpc', i, **overrides),
                context=self.context,
            )
            previous_stack = stack
            plan.add(
                stack=stack,
                run_func=self._run_func,
                requires=stack.requires,
            )

        plan.execute()
        self.assertEqual(self.count, 9)
        self.assertEqual(len(plan.list_skipped()), 1)

    @mock.patch('stacker.plan.multiprocessing')
    def test_execute_plan_with_watchers(self, patched_multiprocessing):
        watch_func = mock.MagicMock()
        plan = Plan(description='Test', sleep_time=0, watch_func=watch_func)
        previous_stack = None
        for i in range(5):
            overrides = {}
            if previous_stack:
                overrides['requires'] = [previous_stack.fqn]
            stack = Stack(
                definition=generate_definition('vpc', i, **overrides),
                context=self.context,
            )
            previous_stack = stack
            plan.add(
                stack=stack,
                run_func=self._run_func,
                requires=stack.requires,
            )

        plan.execute()
        self.assertEqual(self.count, 9)
        self.assertEqual(len(plan.list_skipped()), 1)
        self.assertEqual(patched_multiprocessing.Process().start.call_count, 5)
        # verify we terminate the process when the stack is finished and also
        # redundantly terminate the process after execution
        self.assertEqual(
            patched_multiprocessing.Process().terminate.call_count, 10)

    def test_step_must_return_status(self):
        plan = Plan(description='Test', sleep_time=0)
        stack = Stack(definition=generate_definition('vpc', 1),
                      context=mock.MagicMock())
        plan.add(
            stack=stack,
            run_func=lambda x, **kwargs: (x),
        )
        with self.assertRaises(ValueError):
            plan.execute()

    def test_execute_plan_ensure_parallel_builds(self):
        # key: stack_name, value: current iteration
        work_states = {}
        submitted_state = 0
        # It takes 4 iterations for each task to finish
        finished_state = 3

        def _run_func(stack, *args, **kwargs):
            if stack.name not in work_states:
                work_states[stack.name] = submitted_state
                return SUBMITTED

            if work_states[stack.name] == finished_state:
                return COMPLETE

            work_states[stack.name] += 1
            return SUBMITTED

        vpc_stack = Stack(definition=generate_definition('vpc', 1),
                          context=self.context)
        web_stack = Stack(
            definition=generate_definition('web', 2, requires=[vpc_stack.fqn]),
            context=self.context,
        )
        db_stack = Stack(
            definition=generate_definition('db', 3, requires=[vpc_stack.fqn]),
            context=self.context,
        )

        plan = Plan(description='Test', sleep_time=0)
        for stack in [vpc_stack, web_stack, db_stack]:
            plan.add(
                stack=stack,
                run_func=_run_func,
                requires=stack.requires,
            )

        parallel_success = False
        while not plan._single_run():
            vpc_step = plan[vpc_stack.fqn]
            web_step = plan[web_stack.fqn]
            db_step = plan[db_stack.fqn]
            if not vpc_step.completed:
                self.assertFalse(web_step.submitted)
                self.assertFalse(db_step.submitted)
            else:
                # If the vpc step is complete, and we see both the web & db
                # steps submitted during the same run, then parallel running
                # works
                if web_step.status == SUBMITTED and \
                        db_step.status == SUBMITTED:
                    parallel_success = True
        self.assertTrue(parallel_success)

    def test_plan_wait_func_must_be_function(self):
        with self.assertRaises(ImproperlyConfigured):
            Plan(description='Test', wait_func='invalid')

    def test_plan_steps_listed_with_fqn(self):
        plan = Plan(description='Test', sleep_time=0)
        stack = Stack(definition=generate_definition('vpc', 1),
                      context=self.context)
        plan.add(stack=stack, run_func=lambda x, y: (x, y))
        steps = plan.list_pending()
        self.assertEqual(steps[0][0], stack.fqn)

    def test_execute_plan_wait_func_not_called_if_complete(self):
        wait_func = mock.MagicMock()
        plan = Plan(description='Test', wait_func=wait_func)

        def run_func(*args, **kwargs):
            return COMPLETE

        for i in range(2):
            stack = Stack(definition=generate_definition('vpc', i),
                          context=self.context)
            plan.add(
                stack=stack,
                run_func=run_func,
                requires=stack.requires,
            )

        plan.execute()
        self.assertEqual(wait_func.call_count, 0)

    def test_reset_plan(self):
        plan = Plan(description='Test', sleep_time=0)
        previous_stack = None
        for i in range(5):
            overrides = {}
            if previous_stack:
                overrides['requires'] = [previous_stack.fqn]
            stack = Stack(
                definition=generate_definition('vpc', i, **overrides),
                context=self.context,
            )
            previous_stack = stack
            plan.add(
                stack=stack,
                run_func=self._run_func,
                requires=stack.requires,
            )

        plan.execute()
        self.assertEqual(self.count, 9)
        self.assertEqual(len(plan.list_skipped()), 1)
        plan.reset()
        self.assertEqual(len(plan.list_pending()), len(plan))

    def test_reset_after_outline(self):
        plan = Plan(description='Test', sleep_time=0)
        previous_stack = None
        for i in range(5):
            overrides = {}
            if previous_stack:
                overrides['requires'] = [previous_stack.fqn]
            stack = Stack(
                definition=generate_definition('vpc', i, **overrides),
                context=self.context,
            )
            previous_stack = stack
            plan.add(
                stack=stack,
                run_func=self._run_func,
                requires=stack.requires,
            )

        plan.outline()
        self.assertEqual(len(plan.list_pending()), len(plan))

    @mock.patch('stacker.plan.os')
    @mock.patch('stacker.plan.open', mock.mock_open(), create=True)
    def test_reset_after_dump(self, *args):
        plan = Plan(description='Test', sleep_time=0)
        previous_stack = None
        for i in range(5):
            overrides = {}
            if previous_stack:
                overrides['requires'] = [previous_stack.fqn]
            stack = Stack(
                definition=generate_definition('vpc', i, **overrides),
                context=self.context,
            )
            previous_stack = stack
            plan.add(
                stack=stack,
                run_func=self._run_func,
                requires=stack.requires,
            )

        plan.dump('test')
        self.assertEqual(len(plan.list_pending()), len(plan))
