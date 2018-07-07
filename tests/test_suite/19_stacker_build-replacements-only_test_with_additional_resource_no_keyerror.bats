#!/usr/bin/env bats

load ../test_helper

@test "stacker build - replacements-only test with additional resource, no keyerror" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: add-resource-test-with-replacements-only
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy

EOF
  }

config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: add-resource-test-with-replacements-only
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2

EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "add-resource-test-with-replacements-only: submitted (creating new stack)"
  assert_has_line "add-resource-test-with-replacements-only: complete (creating new stack)"

  # Perform a additional resouce addition in replacements-only mode, should not crash.  This is testing issue #463.
  stacker build -i --replacements-only <(config2)
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "add-resource-test-with-replacements-only: complete (updating existing stack)"

  # Cleanup
  stacker destroy --force <(config2)
  assert "$status" -eq 0
  assert_has_line "add-resource-test-with-replacements-only: submitted (submitted for destruction)"
  assert_has_line "add-resource-test-with-replacements-only: complete (stack destroyed)"
}
