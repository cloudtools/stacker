#!/usr/bin/env bats

load ../test_helper

@test "stacker build - simple build with environment" {
  needs_aws

  environment() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
vpc_public_subnets: 10.128.0.0/24,10.128.1.0/24,10.128.2.0/24,10.128.3.0/24
vpc_private_subnets: 10.128.8.0/22,10.128.12.0/22,10.128.16.0/22,10.128.20.0/22
EOF
  }

  config() {
    cat <<EOF
namespace: \${namespace}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
    variables:
      PublicSubnets: \${vpc_public_subnets}
      PrivateSubnets: \${vpc_private_subnets
EOF
  }

  teardown() {
    stacker destroy --force <(environment) <(config)
  }

  # Create the new stacks.
  stacker build <(environment) <(config)
  assert "$status" -eq 0
}
