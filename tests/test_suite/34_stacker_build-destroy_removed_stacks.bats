#!/usr/bin/env bats

load ../test_helper

@test "stacker build - destroy removed stacks" {
  needs_aws

  environment() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
EOF
  }

  initial_config() {
    cat <<EOF
namespace: \${namespace}
persistent_graph_key: test.json
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    requires:
      - vpc
  - name: other
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  second_config() {
    cat <<EOF
namespace: \${namespace}
persistent_graph_key: test.json
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    requires:
      - vpc
EOF
  }

  teardown() {
    stacker destroy --force <(environment) <(initial_config)
  }

  # Create the new stacks.
  stacker build <(environment) <(initial_config)
  assert "$status" -eq 0

  for stack in vpc bastion other; do
    assert_has_line "${stack}: submitted (creating new stack)"
    assert_has_line "${stack}: complete (creating new stack)"
  done

  # destroy removed stack
  stacker build <(environment) <(second_config)
  assert "$status" -eq 0

  for stack in vpc bastion; do
    assert_has_line "${stack}: skipped (nochange)"
  done

  assert_has_line "other was removed from the Stacker config file so it is being destroyed."
  assert_has_line "other: submitted (submitted for destruction)"
  assert_has_line "other: complete (stack destroyed)"

  # recreate "other" stack
  stacker build <(environment) <(initial_config)
  assert "$status" -eq 0

  for stack in vpc bastion; do
    assert_has_line "${stack}: skipped (nochange)"
  done

  assert_has_line "other: submitted (creating new stack)"
  assert_has_line "other: complete (creating new stack)"

  # destroy removed stack using persistent graph
  stacker destroy --force <(environment) <(initial_config)
  assert "$status" -eq 0

  for stack in vpc bastion other; do
    assert_has_line "${stack}: submitted (submitted for destruction)"
    assert_has_line "${stack}: complete (stack destroyed)"
  done
}
