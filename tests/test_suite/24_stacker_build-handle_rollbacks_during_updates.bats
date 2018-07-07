#!/usr/bin/env bats

load ../test_helper

@test "stacker build - handle rollbacks during updates" {
  needs_aws

  bad_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: update-rollback
    class_path: stacker.tests.fixtures.mock_blueprints.Broken

EOF
  }

  good_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: update-rollback
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy

EOF
  }

  good_config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: update-rollback
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2

EOF
  }

  teardown() {
    stacker destroy --force <(good_config)
  }

  stacker destroy --force <(good_config)

  # Create the initial stack
  stacker build <(good_config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "update-rollback: submitted (creating new stack)"
  assert_has_line "update-rollback: complete (creating new stack)"

  # Do a bad update and watch the rollback
  stacker build <(bad_config)
  assert "$status" -eq 1
  assert_has_line "Using default AWS provider mode"
  assert_has_line "update-rollback: submitted (updating existing stack)"
  assert_has_line "update-rollback: failed (rolled back update)"

  # Do a good update so we know we've correctly waited for rollback
  stacker build <(good_config2)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "update-rollback: submitted (updating existing stack)"
  assert_has_line "update-rollback: complete (updating existing stack)"
}
