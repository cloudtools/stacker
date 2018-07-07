#!/usr/bin/env bats

load ../test_helper

@test "stacker diff - raw template" {
  needs_aws

  config1() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    template_path: ../stacker/tests/fixtures/cfn_template.json
    variables:
      Param1: foobar
EOF
  }

  config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    template_path: ../stacker/tests/fixtures/cfn_template.json
    variables:
      Param1: newbar
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
  assert_has_line "\-Param1 = foobar"
  assert_has_line "+Param1 = newbar"
}
