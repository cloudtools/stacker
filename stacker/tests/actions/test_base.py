from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from future import standard_library
standard_library.install_aliases()

import unittest

from mock import MagicMock, PropertyMock, patch

from stacker.actions.base import (
    BaseAction
)
from stacker.blueprints.base import Blueprint
from stacker.plan import Graph, Step, Plan
from stacker.providers.aws.default import Provider
from stacker.session_cache import get_session

from stacker.tests.factories import (
    MockProviderBuilder,
    mock_context,
)

MOCK_VERSION = "01234abcdef"


class TestBlueprint(Blueprint):
    @property
    def version(self):
        return MOCK_VERSION

    VARIABLES = {
        "Param1": {"default": "default", "type": str},
    }


class TestBaseAction(unittest.TestCase):

    def setUp(self):
        self.region = 'us-east-1'
        self.session = get_session(self.region)
        self.provider = Provider(self.session)

        self.config_no_persist = {
            'stacks': [
                {'name': 'stack1'},
                {'name': 'stack2',
                 'requires': ['stack1']}
            ]
        }

        self.config_persist = {
            'persistent_graph_key': 'test.json',
            'stacks': [
                {'name': 'stack1'},
                {'name': 'stack2',
                 'requires': ['stack1']}
            ]
        }

    @patch('stacker.context.Context._persistent_graph_tags',
           new_callable=PropertyMock)
    @patch('stacker.actions.base.BaseAction._stack_action',
           new_callable=PropertyMock)
    def test_generate_plan_no_persist_exclude(self, mock_stack_action,
                                              mock_tags):
        mock_stack_action.return_value = MagicMock()
        mock_tags.return_value = {}
        context = mock_context(namespace='test',
                               extra_config_args=self.config_no_persist,
                               region=self.region)
        action = BaseAction(context=context,
                            provider_builder=MockProviderBuilder(
                                self.provider, region=self.region))

        plan = action._generate_plan(include_persistent_graph=False)

        mock_tags.assert_not_called()
        self.assertIsInstance(plan, Plan)
        # order is different between python2/3 so can't compare dicts
        result_graph_dict = plan.graph.to_dict()
        self.assertEqual(2, len(result_graph_dict))
        self.assertEqual(set(), result_graph_dict['stack1'])
        self.assertEqual(set(['stack1']), result_graph_dict['stack2'])
        self.assertEqual(BaseAction.DESCRIPTION, plan.description)
        self.assertTrue(plan.require_unlocked)

    @patch('stacker.context.Context._persistent_graph_tags',
           new_callable=PropertyMock)
    @patch('stacker.actions.base.BaseAction._stack_action',
           new_callable=PropertyMock)
    def test_generate_plan_no_persist_include(self, mock_stack_action,
                                              mock_tags):
        mock_stack_action.return_value = MagicMock()
        mock_tags.return_value = {}
        context = mock_context(namespace='test',
                               extra_config_args=self.config_no_persist,
                               region=self.region)
        action = BaseAction(context=context,
                            provider_builder=MockProviderBuilder(
                                self.provider, region=self.region))

        plan = action._generate_plan(include_persistent_graph=True)

        mock_tags.assert_not_called()
        self.assertIsInstance(plan, Plan)
        # order is different between python2/3 so can't compare dicts
        result_graph_dict = plan.graph.to_dict()
        self.assertEqual(2, len(result_graph_dict))
        self.assertEqual(set(), result_graph_dict['stack1'])
        self.assertEqual(set(['stack1']), result_graph_dict['stack2'])
        self.assertEqual(BaseAction.DESCRIPTION, plan.description)
        self.assertTrue(plan.require_unlocked)

    @patch('stacker.context.Context._persistent_graph_tags',
           new_callable=PropertyMock)
    @patch('stacker.actions.base.BaseAction._stack_action',
           new_callable=PropertyMock)
    def test_generate_plan_with_persist_exclude(self, mock_stack_action,
                                                mock_tags):
        mock_stack_action.return_value = MagicMock()
        mock_tags.return_value = {}
        context = mock_context(namespace='test',
                               extra_config_args=self.config_persist,
                               region=self.region)
        persist_step = Step.from_stack_name('removed', context)
        context._persistent_graph = Graph.from_steps([persist_step])
        action = BaseAction(context=context,
                            provider_builder=MockProviderBuilder(
                                self.provider, region=self.region))

        plan = action._generate_plan(include_persistent_graph=False)

        self.assertIsInstance(plan, Plan)
        # order is different between python2/3 so can't compare dicts
        result_graph_dict = plan.graph.to_dict()
        self.assertEqual(2, len(result_graph_dict))
        self.assertEqual(set(), result_graph_dict['stack1'])
        self.assertEqual(set(['stack1']), result_graph_dict['stack2'])
        self.assertEqual(BaseAction.DESCRIPTION, plan.description)
        self.assertTrue(plan.require_unlocked)

    @patch('stacker.context.Context._persistent_graph_tags',
           new_callable=PropertyMock)
    @patch('stacker.actions.base.BaseAction._stack_action',
           new_callable=PropertyMock)
    def test_generate_plan_with_persist_include(self, mock_stack_action,
                                                mock_tags):
        mock_stack_action.return_value = MagicMock()
        mock_tags.return_value = {}
        context = mock_context(namespace='test',
                               extra_config_args=self.config_persist,
                               region=self.region)
        persist_step = Step.from_stack_name('removed', context)
        context._persistent_graph = Graph.from_steps([persist_step])
        action = BaseAction(context=context,
                            provider_builder=MockProviderBuilder(
                                self.provider, region=self.region))

        plan = action._generate_plan(include_persistent_graph=True)

        self.assertIsInstance(plan, Plan)
        mock_tags.assert_called_once()
        # order is different between python2/3 so can't compare dicts
        result_graph_dict = plan.graph.to_dict()
        self.assertEqual(3, len(result_graph_dict))
        self.assertEqual(set(), result_graph_dict['stack1'])
        self.assertEqual(set(['stack1']), result_graph_dict['stack2'])
        self.assertEqual(set(), result_graph_dict['removed'])
        self.assertEqual(BaseAction.DESCRIPTION, plan.description)
        self.assertTrue(plan.require_unlocked)

    @patch('stacker.context.Context._persistent_graph_tags',
           new_callable=PropertyMock)
    @patch('stacker.actions.base.BaseAction._stack_action',
           new_callable=PropertyMock)
    def test_generate_plan_with_persist_no_lock_req(self, mock_stack_action,
                                                    mock_tags):
        mock_stack_action.return_value = MagicMock()
        mock_tags.return_value = {}
        context = mock_context(namespace='test',
                               extra_config_args=self.config_persist,
                               region=self.region)
        persist_step = Step.from_stack_name('removed', context)
        context._persistent_graph = Graph.from_steps([persist_step])
        action = BaseAction(context=context,
                            provider_builder=MockProviderBuilder(
                                self.provider, region=self.region))

        plan = action._generate_plan(include_persistent_graph=True,
                                     require_unlocked=False)

        self.assertIsInstance(plan, Plan)
        mock_tags.assert_called_once()
        # order is different between python2/3 so can't compare dicts
        result_graph_dict = plan.graph.to_dict()
        self.assertEqual(3, len(result_graph_dict))
        self.assertEqual(set(), result_graph_dict['stack1'])
        self.assertEqual(set(['stack1']), result_graph_dict['stack2'])
        self.assertEqual(set(), result_graph_dict['removed'])
        self.assertEqual(BaseAction.DESCRIPTION, plan.description)
        self.assertFalse(plan.require_unlocked)

    def test_stack_template_url(self):
        context = mock_context("mynamespace")
        blueprint = TestBlueprint(name="myblueprint", context=context)

        region = "us-east-1"
        endpoint = "https://example.com"
        session = get_session(region)
        provider = Provider(session)
        action = BaseAction(
            context=context,
            provider_builder=MockProviderBuilder(provider, region=region)
        )

        with patch('stacker.actions.base.get_s3_endpoint', autospec=True,
                   return_value=endpoint):
            self.assertEqual(
                action.stack_template_url(blueprint),
                "%s/%s/stack_templates/%s/%s-%s.json" % (
                    endpoint,
                    "stacker-mynamespace",
                    "mynamespace-myblueprint",
                    "myblueprint",
                    MOCK_VERSION
                )
            )
