#!/usr/bin/env bats

load ../test_helper

@test "stacker build - raw template parameter resolution" {
  needs_aws

  echo "PWD: $PWD"

  SECRET_VALUE="foo-secret"
  DEFAULT_SECRET_VALUE="default-secret"

  NORMAL_VALUE="foo"
  CHANGED_NORMAL_VALUE="foo-changed"

  initial_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    template_path: ../stacker/tests/fixtures/parameter_resolution/template.yml
    variables:
      NormalParam: ${NORMAL_VALUE}
      SecretParam: ${SECRET_VALUE}
EOF
  }

  # Remove the value for SecretParam - should use the existing value if a stack
  # exists, if not should use the default
  no_secret_value_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    template_path: ../stacker/tests/fixtures/parameter_resolution/template.yml
    variables:
      NormalParam: ${NORMAL_VALUE}
EOF
  }

  # Remove the value for SecretParam - should use the existing value if a stack
  # exists, if not should use the default
  no_secret_value_change_normal_value_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    template_path: ../stacker/tests/fixtures/parameter_resolution/template.yml
    variables:
      NormalParam: ${CHANGED_NORMAL_VALUE}
EOF
  }


  teardown() {
    stacker destroy --force <(initial_config)
  }

  # Create the new stacks.
  stacker build <(initial_config)
  assert "$status" -eq 0
  assert_has_line "vpc: complete (creating new stack)"

  # Update without providing secret value, should use existing value, so
  # no change
  stacker build <(no_secret_value_config)
  assert "$status" -eq 0
  assert_has_line "vpc: skipped (nochange)"

  # Update without providing secret value, should use existing value, but
  # update the normal value - so should update
  stacker build <(no_secret_value_change_normal_value_config)
  assert "$status" -eq 0
  assert_has_line "vpc: complete (updating existing stack)"

  # Check that the normal value changed
  stacker info <(no_secret_value_change_normal_value_config)
  assert "$status" -eq 0
  assert_has_line "NormalParam: ${CHANGED_NORMAL_VALUE}"

  # Check that we used the previous value
  stacker info <(no_secret_value_config)
  assert "$status" -eq 0
  assert_has_line "SecretParam: ${SECRET_VALUE}"

  # Cleanup
  stacker destroy --force <(initial_config)
  assert "$status" -eq 0
  assert_has_line "vpc: complete (stack destroyed)"

  # Create the new stacks but with no secret parameter, should use the default
  stacker build <(no_secret_value_config)
  assert "$status" -eq 0
  assert_has_line "vpc: complete (creating new stack)"

  # Check that we used the default value
  stacker info <(no_secret_value_config)
  assert "$status" -eq 0
  assert_has_line "SecretParam: ${DEFAULT_SECRET_VALUE}"
}
