#!/usr/bin/env bats

load ../test_helper

@test "stacker build - raw template" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    template_path: ../stacker/tests/fixtures/cfn_template.json
    variables:
      Param1: foobar
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "vpc: submitted (creating new stack)"
  assert_has_line "vpc: complete (creating new stack)"

  # Perform a noop update to the stacks, in interactive mode.
  stacker build -i <(config)
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "vpc: skipped (nochange)"

  # Cleanup
  stacker destroy --force <(config)
  assert "$status" -eq 0
  assert_has_line "vpc: submitted (submitted for destruction)"
  assert_has_line "vpc: complete (stack destroyed)"
}
