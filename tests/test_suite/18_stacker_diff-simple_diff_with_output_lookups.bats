#!/usr/bin/env bats

load ../test_helper

@test "stacker diff - simple diff with output lookups" {
  needs_aws

  config1() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.DiffTester
    variables:
      InstanceType: m3.large
      WaitConditionCount: 1
EOF
  }

  config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.DiffTester
    variables:
      InstanceType: m3.xlarge
      WaitConditionCount: 2
EOF
  }

  teardown() {
    stacker destroy --force <(config1)
  }

  # Create the new stacks.
  stacker build <(config1)
  assert "$status" -eq 0

  stacker diff <(config2)
  assert "$status" -eq 0
  assert_has_line "\-InstanceType = m3.large"
  assert_has_line "+InstanceType = m3.xlarge"
  assert_has_line "+         \"VPC1\": {"
  assert_has_line "+             \"Type\": \"AWS::CloudFormation::WaitConditionHandle\""
}
