#!/usr/bin/env bats

load ../test_helper

@test "stacker build - config with no stacks" {
  needs_aws

  stacker build - <<EOF
namespace: ${STACKER_NAMESPACE}
EOF
  assert "$status" -eq 0
  assert_has_line 'WARNING: No stacks detected (error in config?)'
}
