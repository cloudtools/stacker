#!/usr/bin/env bats

load ../test_helper

@test "stacker build - missing environment key" {
  environment() {
    cat <<EOF
vpc_private_subnets: 10.128.8.0/22,10.128.12.0/22,10.128.16.0/22,10.128.20.0/22
EOF
  }

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
    variables:
      PublicSubnets: \${vpc_public_subnets}
      PrivateSubnets: \${vpc_private_subnets
EOF
  }

  # Create the new stacks.
  stacker build <(environment) <(config)
  assert ! "$status" -eq 0
  assert_has_line "stacker.exceptions.MissingEnvironment: Environment missing key vpc_public_subnets."
}
