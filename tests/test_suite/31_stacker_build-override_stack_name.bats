#!/usr/bin/env bats

load ../test_helper

@test "stacker build - override stack name" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    stack_name: vpcx
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    variables:
      StringVariable: \${output vpc::DummyId}
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
  assert_has_line "bastion: submitted (creating new stack)"
  assert_has_line "bastion: complete (creating new stack)"
}
