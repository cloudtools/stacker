#!/usr/bin/env bats

load ../test_helper

@test "stacker build - handle rollbacks in dependent stacks" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: dependent-rollback-parent
    class_path: stacker.tests.fixtures.mock_blueprints.Broken

  - name: dependent-rollback-child
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    requires: [dependent-rollback-parent]

EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  stacker destroy --force <(config)

  # Verify both stacks fail during creation
  stacker build -v <(config)
  assert "$status" -eq 1
  assert_has_line "Using default AWS provider mode"
  assert_has_line "dependent-rollback-parent: submitted (creating new stack)"
  assert_has_line "dependent-rollback-parent: submitted (rolling back new stack)"
  assert_has_line "dependent-rollback-parent: failed (rolled back new stack)"
  assert_has_line "dependent-rollback-child: failed (dependency has failed)"
  assert_has_line "The following steps failed: dependent-rollback-parent, dependent-rollback-child"
}
