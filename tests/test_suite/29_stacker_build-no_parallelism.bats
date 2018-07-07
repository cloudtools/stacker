#!/usr/bin/env bats

load ../test_helper

@test "stacker build - no parallelism" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc1
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: vpc2
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build -j 1 <(config)
  assert "$status" -eq 0
  assert_has_line "vpc1: submitted (creating new stack)"
  assert_has_line "vpc1: complete (creating new stack)"
  assert_has_line "vpc2: submitted (creating new stack)"
  assert_has_line "vpc2: complete (creating new stack)"
}
