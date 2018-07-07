#!/usr/bin/env bats

load ../test_helper

@test "stacker build - overriden environment key with -e" {
  needs_aws

  environment() {
    cat <<EOF
namespace: stacker
EOF
  }

  config() {
    cat <<EOF
namespace: \${namespace}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
    variables:
      PublicSubnets: 10.128.0.0/24,10.128.1.0/24,10.128.2.0/24,10.128.3.0/24
      PrivateSubnets: 10.128.8.0/22,10.128.12.0/22,10.128.16.0/22,10.128.20.0/22
EOF
  }

  teardown() {
    stacker destroy -e namespace=$STACKER_NAMESPACE --force <(environment) <(config)
  }

  # Create the new stacks.
  stacker build -e namespace=$STACKER_NAMESPACE <(environment) <(config)
  assert "$status" -eq 0
  assert_has_line "vpc: submitted (creating new stack)"
}
