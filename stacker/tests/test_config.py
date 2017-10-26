import sys
import unittest

from stacker.config import (
    render_parse_load,
    load,
    render,
    parse,
    dump,
    process_remote_sources
)
from stacker.config import Config, Stack
from stacker.environment import parse_environment
from stacker import exceptions
from stacker.lookups.registry import LOOKUP_HANDLERS

from yaml.constructor import ConstructorError

config = """a: $a
b: $b
c: $c"""


class TestConfig(unittest.TestCase):
    def test_render_missing_env(self):
        env = {"a": "A"}
        with self.assertRaises(exceptions.MissingEnvironment) as expected:
            render(config, env)
        self.assertEqual(expected.exception.key, "b")

    def test_render_no_variable_config(self):
        c = render("namespace: prod", {})
        self.assertEqual("namespace: prod", c)

    def test_render_valid_env_substitution(self):
        c = render("namespace: $namespace", {"namespace": "prod"})
        self.assertEqual("namespace: prod", c)

    def test_render_blank_env_values(self):
        conf = """namespace: ${namespace}"""
        e = parse_environment("""namespace:""")
        c = render(conf, e)
        self.assertEqual("namespace: ", c)
        e = parse_environment("""namespace: !!str""")
        c = render(conf, e)
        self.assertEqual("namespace: !!str", c)

    def test_config_validate_missing_stack_class_path(self):
        config = Config({
            "namespace": "prod",
            "stacks": [
                {
                    "name": "bastion"}]})
        with self.assertRaises(exceptions.InvalidConfig) as ex:
            config.validate()

        error = ex.exception.errors['stacks'][0]['class_path'].errors[0]
        self.assertEquals(
            error.__str__(),
            "This field is required.")

    def test_config_validate_no_stacks(self):
        config = Config({"namespace": "prod"})
        with self.assertRaises(exceptions.InvalidConfig) as ex:
            config.validate()

        error = ex.exception.errors['stacks'].errors[0]
        self.assertEquals(
            error.__str__(),
            "Should have more than one element.")

    def test_config_validate_missing_name(self):
        config = Config({
            "namespace": "prod",
            "stacks": [
                {
                    "class_path": "blueprints.Bastion"}]})
        with self.assertRaises(exceptions.InvalidConfig) as ex:
            config.validate()

        error = ex.exception.errors['stacks'][0]['name'].errors[0]
        self.assertEquals(
            error.__str__(),
            "This field is required.")

    def test_config_validate_duplicate_stack_names(self):
        config = Config({
            "namespace": "prod",
            "stacks": [
                {
                    "name": "bastion",
                    "class_path": "blueprints.Bastion"},
                {
                    "name": "bastion",
                    "class_path": "blueprints.BastionV2"}]})
        with self.assertRaises(exceptions.InvalidConfig) as ex:
            config.validate()

        error = ex.exception.errors['stacks'][0]
        self.assertEquals(
            error.__str__(),
            "Duplicate stack bastion found at index 0.")

    def test_dump_unicode(self):
        config = Config()
        config.namespace = "test"
        self.assertEquals(dump(config), """namespace: test
stacks: []
""")

        config = Config({"namespace": "test"})
        # Ensure that we're producing standard yaml, that doesn't include
        # python specific objects.
        self.assertNotEquals(
            dump(config), "namespace: !!python/unicode 'test'\n")
        self.assertEquals(dump(config), """namespace: test
stacks: []
""")

    def test_parse_tags(self):
        config = parse("""
        namespace: prod
        tags:
          "a:b": "c"
          "hello": 1
          simple_tag: simple value
        """)
        self.assertEquals(config.tags, {
            "a:b": "c",
            "hello": "1",
            "simple_tag": "simple value"})

    def test_parse_with_arbitrary_anchors(self):
        config = parse("""
        namespace: prod
        common_variables: &common_variables
          Foo: bar
        stacks:
        - name: vpc
          class_path: blueprints.VPC
          variables:
            << : *common_variables
        """)

        stack = config.stacks[0]
        self.assertEquals(stack.variables, {"Foo": "bar"})

    def test_parse_with_deprecated_parameters(self):
        config = parse("""
        namespace: prod
        stacks:
        - name: vpc
          class_path: blueprints.VPC
          parameters:
            Foo: bar
        """)
        with self.assertRaises(exceptions.InvalidConfig) as ex:
            config.validate()

        error = ex.exception.errors['stacks'][0]['parameters'][0]
        self.assertEquals(
            error.__str__(),
            "DEPRECATION: Stack definition vpc contains deprecated "
            "'parameters', rather than 'variables'. You are required to update"
            " your config. See https://stacker.readthedocs.io/en/latest/c"
            "onfig.html#variables for additional information.")

    def test_config_build(self):
        vpc = Stack({"name": "vpc", "class_path": "blueprints.VPC"})
        config = Config({"namespace": "prod", "stacks": [vpc]})
        self.assertEquals(config.namespace, "prod")
        self.assertEquals(config.stacks[0].name, "vpc")
        self.assertEquals(config["namespace"], "prod")
        config.validate()

    def test_parse(self):
        config_with_lists = """
        namespace: prod
        stacker_bucket: stacker-prod
        pre_build:
          - path: stacker.hooks.route53.create_domain
            required: true
            args:
              domain: mydomain.com
        post_build:
          - path: stacker.hooks.route53.create_domain
            required: true
            args:
              domain: mydomain.com
        pre_destroy:
          - path: stacker.hooks.route53.create_domain
            required: true
            args:
              domain: mydomain.com
        post_destroy:
          - path: stacker.hooks.route53.create_domain
            required: true
            args:
              domain: mydomain.com
        package_sources:
          git:
            - uri: git@github.com:acmecorp/stacker_blueprints.git
            - uri: git@github.com:remind101/stacker_blueprints.git
              tag: 1.0.0
              paths:
                - stacker_blueprints
            - uri: git@github.com:contoso/webapp.git
              branch: staging
            - uri: git@github.com:contoso/foo.git
              commit: 12345678
        tags:
          environment: production
        stacks:
        - name: vpc
          class_path: blueprints.VPC
          variables:
            PrivateSubnets:
            - 10.0.0.0/24
        - name: bastion
          class_path: blueprints.Bastion
          requires: ['vpc']
          variables:
            VpcId: ${output vpc::VpcId}
        """
        config_with_dicts = """
        namespace: prod
        stacker_bucket: stacker-prod
        pre_build:
          prebuild_createdomain:
            path: stacker.hooks.route53.create_domain
            required: true
            args:
              domain: mydomain.com
        post_build:
          postbuild_createdomain:
            path: stacker.hooks.route53.create_domain
            required: true
            args:
              domain: mydomain.com
        pre_destroy:
          predestroy_createdomain:
            path: stacker.hooks.route53.create_domain
            required: true
            args:
              domain: mydomain.com
        post_destroy:
          postdestroy_createdomain:
            path: stacker.hooks.route53.create_domain
            required: true
            args:
              domain: mydomain.com
        package_sources:
          git:
            - uri: git@github.com:acmecorp/stacker_blueprints.git
            - uri: git@github.com:remind101/stacker_blueprints.git
              tag: 1.0.0
              paths:
                - stacker_blueprints
            - uri: git@github.com:contoso/webapp.git
              branch: staging
            - uri: git@github.com:contoso/foo.git
              commit: 12345678
        tags:
          environment: production
        stacks:
          vpc:
            class_path: blueprints.VPC
            variables:
              PrivateSubnets:
              - 10.0.0.0/24
          bastion:
            class_path: blueprints.Bastion
            requires: ['vpc']
            variables:
              VpcId: ${output vpc::VpcId}
        """

        for raw_config in [config_with_lists, config_with_dicts]:
            config = parse(raw_config)

            config.validate()

            self.assertEqual(config.namespace, "prod")
            self.assertEqual(config.stacker_bucket, "stacker-prod")

            for hooks in [config.pre_build, config.post_build,
                          config.pre_destroy, config.post_destroy]:
                self.assertEqual(
                    hooks[0].path, "stacker.hooks.route53.create_domain")
                self.assertEqual(
                    hooks[0].required, True)
                self.assertEqual(
                    hooks[0].args, {"domain": "mydomain.com"})

            self.assertEqual(
                config.package_sources.git[0].uri,
                "git@github.com:acmecorp/stacker_blueprints.git")
            self.assertEqual(
                config.package_sources.git[1].uri,
                "git@github.com:remind101/stacker_blueprints.git")
            self.assertEqual(
                config.package_sources.git[1].tag,
                "1.0.0")
            self.assertEqual(
                config.package_sources.git[1].paths,
                ["stacker_blueprints"])
            self.assertEqual(
                config.package_sources.git[2].branch,
                "staging")

            self.assertEqual(config.tags, {"environment": "production"})

            self.assertEqual(len(config.stacks), 2)

            vpc_index = next(
                i for (i, d) in enumerate(config.stacks) if d.name == "vpc"
            )
            vpc = config.stacks[vpc_index]
            self.assertEqual(vpc.name, "vpc")
            self.assertEqual(vpc.class_path, "blueprints.VPC")
            self.assertEqual(vpc.requires, None)
            self.assertEqual(vpc.variables,
                             {"PrivateSubnets": ["10.0.0.0/24"]})

            bastion_index = next(
                i for (i, d) in enumerate(config.stacks) if d.name == "bastion"
            )
            bastion = config.stacks[bastion_index]
            self.assertEqual(bastion.name, "bastion")
            self.assertEqual(bastion.class_path, "blueprints.Bastion")
            self.assertEqual(bastion.requires, ["vpc"])
            self.assertEqual(bastion.variables,
                             {"VpcId": "${output vpc::VpcId}"})

    def test_dump_complex(self):
        config = Config({
            "namespace": "prod",
            "stacks": [
                Stack({
                    "name": "vpc",
                    "class_path": "blueprints.VPC"}),
                Stack({
                    "name": "bastion",
                    "class_path": "blueprints.Bastion",
                    "requires": ["vpc"]})]})

        self.assertEqual(dump(config), """namespace: prod
stacks:
- class_path: blueprints.VPC
  enabled: true
  locked: false
  name: vpc
  protected: false
- class_path: blueprints.Bastion
  enabled: true
  locked: false
  name: bastion
  protected: false
  requires:
  - vpc
""")

    def test_load_register_custom_lookups(self):
        config = Config({
            "lookups": {
                "custom": "importlib.import_module"}})
        load(config)
        self.assertTrue(callable(LOOKUP_HANDLERS["custom"]))

    def test_load_adds_sys_path(self):
        config = Config({"sys_path": "/foo/bar"})
        load(config)
        self.assertIn("/foo/bar", sys.path)

    def test_process_empty_remote_sources(self):
        config = """
        namespace: prod
        stacks:
          - name: vpc
            class_path: blueprints.VPC
        """
        self.assertEqual(config, process_remote_sources(config))

    def test_lookup_with_sys_path(self):
        config = Config({
            "sys_path": "stacker/tests",
            "lookups": {
                "custom": "fixtures.mock_lookups.handler"}})
        load(config)
        self.assertTrue(callable(LOOKUP_HANDLERS["custom"]))

    def test_render_parse_load_namespace_fallback(self):
        conf = """
        stacks:
        - name: vpc
          class_path: blueprints.VPC
        """
        config = render_parse_load(
            conf, environment={"namespace": "prod"}, validate=False)
        config.validate()
        self.assertEquals(config.namespace, "prod")

    def test_raise_constructor_error_on_duplicate_key(self):
        yaml_config = """
        namespace: prod
        stacks:
          - name: vpc
            class_path: blueprints.VPC
            class_path: blueprints.Fake
        """
        with self.assertRaises(ConstructorError):
            parse(yaml_config)

    def test_raise_construct_error_on_duplicate_stack_name(self):
        yaml_config = """
        namespace: prod
        stacks:
          my_vpc:
            class_path: blueprints.VPC1
          my_vpc:
            class_path: blueprints.VPC2
        """
        with self.assertRaises(ConstructorError):
            parse(yaml_config)


if __name__ == '__main__':
    unittest.main()
