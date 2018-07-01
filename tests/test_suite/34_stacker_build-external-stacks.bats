#!/usr/bin/env bats

load ../test_helper

@test "stacker build - external stack" {
  needs_aws

  config1() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc/west
    stack_name: external-vpc
    profile: stacker
    region: us-west-1
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: vpc/east
    stack_name: external-vpc
    profile: stacker
    region: us-east-1
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc/west
    stack_name: external-vpc
    profile: stacker
    region: us-west-1
    external: yes
  - name: vpc/east
    fqn: ${STACKER_NAMESPACE}-external-vpc
    profile: stacker
    region: us-east-1
    external: yes
  - name: vpc/combo
    stack_name: vpc
    profile: stacker
    region: us-east-1
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    variables:
      StringVariable: >-
        \${output vpc/west::Region}
        \${output vpc/east::Region}
EOF
  }

  teardown() {
    stacker destroy --force <(config2)
    stacker destroy --force <(config1)
  }

  # Create the new stacks.
  stacker build <(config1)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "vpc/west: submitted (creating new stack)"
  assert_has_line "vpc/west: complete (creating new stack)"
  assert_has_line "vpc/east: submitted (creating new stack)"
  assert_has_line "vpc/east: complete (creating new stack)"

  stacker build <(config2)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "vpc/combo: submitted (creating new stack)"
  assert_has_line "vpc/combo: complete (creating new stack)"

  stacker info <(config2)
  assert_has_line "StringOutput: us-west-1 us-east-1"

}
