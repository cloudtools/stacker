#!/usr/bin/env bats

load ../test_helper

@test "stacker build - multi region" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: west/vpc
    region: us-west-1
    stack_name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: east/vpc
    region: us-east-1
    stack_name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: app
    region: us-east-1
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    variables:
      StringVariable: \${output west/vpc::DummyId}
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "vpc: submitted (creating new stack)"
  assert_has_line "vpc: complete (creating new stack)"
  assert_has_line "app: submitted (creating new stack)"
  assert_has_line "app: complete (creating new stack)"

  config_simple() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: west/vpc
    region: us-west-1
    stack_name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  # Assert that the vpc stack was built in us-west-1
  stacker info <(config_simple)
  assert_has_line "Region: us-west-1"
}
