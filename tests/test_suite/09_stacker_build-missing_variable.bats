#!/usr/bin/env bats

load ../test_helper

@test "stacker build - missing variable" {
  needs_aws

  stacker build - <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
EOF
  assert ! "$status" -eq 0
  assert_has_line -E 'MissingVariable: Variable "(PublicSubnets|PrivateSubnets)" in blueprint "vpc" is missing'
  assert_has_line -E 'vpc: failed \(Variable "(PublicSubnets|PrivateSubnets)" in blueprint "vpc" is missing\)'
}
