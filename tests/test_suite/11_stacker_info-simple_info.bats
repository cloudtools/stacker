#!/usr/bin/env bats

load ../test_helper

@test "stacker info - simple info" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0

  stacker info <(config)
  assert "$status" -eq 0
  assert_has_line "Outputs for stacks: ${STACKER_NAMESPACE}"
  assert_has_line "vpc:"
  assert_has_line "DummyId: dummy-1234"
}
