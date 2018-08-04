#!/usr/bin/env bats

load ../test_helper

@test "stacker build - recreate failed stack, interactive mode" {
  needs_aws

  bad_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: recreate-failed-interactive
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
  - name: recreate-failed-interactive
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
  assert_has_line "recreate-failed-interactive: submitted (creating new stack)"
  assert_has_line "recreate-failed-interactive: failed (rolled back new stack)"

  # Updating the stack should prompt to re-create it.
  stacker build -i <(good_config) <<< $'y\n'
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "recreate-failed-interactive: submitted (destroying stack for re-creation)"
  assert_has_line "recreate-failed-interactive: submitted (creating new stack)"
  assert_has_line "recreate-failed-interactive: complete (creating new stack)"

  # Confirm the stack is really updated
  stacker build -i <(good_config)
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "recreate-failed-interactive: skipped (nochange)"

  # Cleanup
  stacker destroy --force <(good_config)
  assert "$status" -eq 0
  assert_has_line "recreate-failed-interactive: submitted (submitted for destruction)"
  assert_has_line "recreate-failed-interactive: complete (stack destroyed)"
}
