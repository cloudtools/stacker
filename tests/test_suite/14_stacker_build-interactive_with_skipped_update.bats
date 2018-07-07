#!/usr/bin/env bats

load ../test_helper

@test "stacker build - interactive with skipped update" {
  needs_aws

  config1() {
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

  config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2
    requires: [vpc]
EOF
  }

  teardown() {
    stacker destroy --force <(config1)
  }

  # Create the new stacks.
  stacker build <(config1)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "vpc: submitted (creating new stack)"
  assert_has_line "vpc: complete (creating new stack)"
  assert_has_line "bastion: submitted (creating new stack)"
  assert_has_line "bastion: complete (creating new stack)"

  # Attempt an update to all stacks, but skip the vpc update.
  stacker build -i <(config2) <<< $'n\ny\n'
  assert "$status" -eq 0
  assert_has_line "vpc: skipped (canceled execution)"
  assert_has_line "bastion: submitted (updating existing stack)"
}
