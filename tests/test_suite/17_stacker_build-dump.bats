#!/usr/bin/env bats

load ../test_helper

@test "stacker build - dump" {
  needs_aws

  config() {
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

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0

  stacker build -d "$TMP" <(config)
  assert "$status" -eq 0
}
