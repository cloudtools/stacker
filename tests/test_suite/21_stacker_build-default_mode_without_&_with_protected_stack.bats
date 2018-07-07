#!/usr/bin/env bats

load ../test_helper

@test "stacker build - default mode, without & with protected stack" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: mystack
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    protected: ${PROTECTED}

EOF
  }

  config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: mystack
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2
  
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # First create the stack
  stacker build --interactive <(PROTECTED="false" config)
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "mystack: submitted (creating new stack)"
  assert_has_line "mystack: complete (creating new stack)"

  # Perform a additional resouce addition in interactive mode, non-protected stack
  stacker build --interactive <(config2) < <(echo "y")
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "mystack: submitted (updating existing stack)"
  assert_has_line "mystack: complete (updating existing stack)"
  assert_has_line "Add Dummy2"

  # Perform another update, this time without interactive, but with a protected stack
  stacker build <(PROTECTED="true" config) < <(echo "y")
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "mystack: submitted (updating existing stack)"
  assert_has_line "mystack: complete (updating existing stack)"
  assert_has_line "Remove Dummy2"

  # Cleanup
  stacker destroy --force <(config2)
  assert "$status" -eq 0
  assert_has_line "mystack: submitted (submitted for destruction)"
  assert_has_line "mystack: complete (stack destroyed)"
}
