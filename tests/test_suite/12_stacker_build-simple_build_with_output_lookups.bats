#!/usr/bin/env bats

load ../test_helper

@test "stacker build - simple build with output lookups" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
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

  for stack in vpc bastion; do
    assert_has_line "${stack}: submitted (creating new stack)"
    assert_has_line "${stack}: complete (creating new stack)"
  done
}
