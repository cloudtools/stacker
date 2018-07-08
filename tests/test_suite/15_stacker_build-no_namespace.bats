#!/usr/bin/env bats

load ../test_helper

@test "stacker build - no namespace" {
  needs_aws

  config() {
    cat <<EOF
namespace: ""
stacks:
  - name: vpc
    stack_name: ${STACKER_NAMESPACE}-vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0
}
