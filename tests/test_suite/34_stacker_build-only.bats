#!/usr/bin/env bats

load ../test_helper

@test "stacker build - only" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: db
    requires: [vpc]
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: app
    requires: [db]
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0

  stacker build --only --stacks app <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "db: skipped (locked)"
  assert_has_line "app: skipped (nochange)"
  assert_has_line -v "vpc"
}
