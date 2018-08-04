#!/usr/bin/env bats

load ../test_helper

@test "stacker build - recreate failed stack, non-interactive mode" {
  needs_aws

  bad_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: recreate-failed
    class_path: stacker.tests.fixtures.mock_blueprints.LongRunningDummy
    variables:
      Count: 10
      BreakLast: true

EOF
  }

  good_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: recreate-failed
    class_path: stacker.tests.fixtures.mock_blueprints.LongRunningDummy
    variables:
      Count: 10
      BreakLast: false
      OutputValue: GoodOutput

EOF
  }

  teardown() {
    stacker destroy --force <(good_config)
  }

  stacker destroy --force <(good_config)

  # Create the initial stack. This must fail.
  stacker build -v <(bad_config)
  assert "$status" -eq 1
  assert_has_line "Using default AWS provider mode"
  assert_has_line "recreate-failed: submitted (creating new stack)"
  assert_has_line "recreate-failed: failed (rolled back new stack)"

  # Updating the stack should prompt to re-create it.
  stacker build --recreate-failed <(good_config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "recreate-failed: submitted (destroying stack for re-creation)"
  assert_has_line "recreate-failed: submitted (creating new stack)"
  assert_has_line "recreate-failed: complete (creating new stack)"

  # Confirm the stack is really updated
  stacker build <(good_config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "recreate-failed: skipped (nochange)"

  # Cleanup
  stacker destroy --force <(good_config)
  assert "$status" -eq 0
  assert_has_line "recreate-failed: submitted (submitted for destruction)"
  assert_has_line "recreate-failed: complete (stack destroyed)"
}
