#!/usr/bin/env bats

load test_helper

@test "stacker build - no config" {
  stacker build
  assert ! "$status" -eq 0
  assert_has_line "stacker build: error: too few arguments"
}

@test "stacker build - empty config" {
  stacker build <(echo "")
  assert ! "$status" -eq 0
  assert_has_line 'Should have more than one element'
}

@test "stacker build - config with no stacks" {
  stacker build - <<EOF
namespace: ${STACKER_NAMESPACE}
EOF
  assert ! "$status" -eq 0
  assert_has_line 'Should have more than one element'
}

@test "stacker build - config with no namespace" {
  stacker build - <<EOF
stacker_bucket: stacker-${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
EOF
  assert ! "$status" -eq 0
  assert_has_line "This field is required"
}

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

@test "stacker build - duplicate stacks" {
  stacker build - <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  assert ! "$status" -eq 0
  assert_has_line "Duplicate stack vpc found"
}

@test "stacker build - missing variable" {
  needs_aws

  stacker build - <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
EOF
  assert ! "$status" -eq 0
  assert_has_line "MissingVariable: Variable \"PublicSubnets\" in blueprint \"vpc\" is missing"
  assert_has_line "${STACKER_NAMESPACE}-vpc: failed (Variable \"PublicSubnets\" in blueprint \"vpc\" is missing)"
}

@test "stacker build - simple build" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.VPC
    variables:
      PublicSubnets: 10.128.0.0/24,10.128.1.0/24,10.128.2.0/24,10.128.3.0/24
      PrivateSubnets: 10.128.8.0/22,10.128.12.0/22,10.128.16.0/22,10.128.20.0/22
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-vpc: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-vpc: complete (creating new stack)"

  # Perform a noop update to the stacks, in interactive mode.
  stacker build -i <(config)
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-vpc: skipped (nochange)"

  # Cleanup
  stacker destroy --force <(config)
  assert "$status" -eq 0
  assert_has_line "${STACKER_NAMESPACE}-vpc: submitted (submitted for destruction)"
  assert_has_line "${STACKER_NAMESPACE}-vpc: complete (stack destroyed)"
}

@test "stacker build - simple build with output lookups" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    variables:
      StringVariable: \${output vpc::DummyId}
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"

  for stack in vpc bastion; do
    assert_has_line "${STACKER_NAMESPACE}-${stack}: submitted (creating new stack)"
    assert_has_line "${STACKER_NAMESPACE}-${stack}: complete (creating new stack)"
  done
}

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

@test "stacker build - interactive with skipped update" {
  needs_aws

  config1() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    requires: [vpc]
EOF
  }

  config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2
    requires: [vpc]
EOF
  }

  teardown() {
    stacker destroy --force <(config1)
  }

  # Create the new stacks.
  stacker build <(config1)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-vpc: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-vpc: complete (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-bastion: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-bastion: complete (creating new stack)"

  # Attempt an update to all stacks, but skip the vpc update.
  stacker build -i <(config2) <<< $'n\ny\n'
  assert "$status" -eq 0
  assert_has_line "${STACKER_NAMESPACE}-vpc: skipped (canceled execution)"
  assert_has_line "${STACKER_NAMESPACE}-bastion: submitted (updating existing stack)"
}

@test "stacker build - no namespace" {
  needs_aws

  config() {
    cat <<EOF
namespace: ""
stacks:
  - name: ${STACKER_NAMESPACE}-vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0
}

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
  assert_has_line "${STACKER_NAMESPACE}-vpc: submitted (creating new stack)"
}

@test "stacker build - dump" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    variables:
      StringVariable: \${output vpc::DummyId}
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build <(config)
  assert "$status" -eq 0

  stacker build -d "$TMP" <(config)
  assert "$status" -eq 0
}

@test "stacker diff - simple diff with output lookups" {
  needs_aws

  config1() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.DiffTester
    variables:
      InstanceType: m3.large
      WaitConditionCount: 1
EOF
  }

  config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.DiffTester
    variables:
      InstanceType: m3.xlarge
      WaitConditionCount: 2
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
  assert_has_line "\-InstanceType = m3.large"
  assert_has_line "+InstanceType = m3.xlarge"
  assert_has_line "+         \"VPC1\": {"
  assert_has_line "+             \"Type\": \"AWS::CloudFormation::WaitConditionHandle\""
}

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
  assert_has_line "${STACKER_NAMESPACE}-add-resource-test-with-replacements-only: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-add-resource-test-with-replacements-only: complete (creating new stack)"

  # Perform a additional resouce addition in replacements-only mode, should not crash.  This is testing issue #463.
  stacker build -i --replacements-only <(config2)
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-add-resource-test-with-replacements-only: complete (updating existing stack)"

  # Cleanup
  stacker destroy --force <(config2)
  assert "$status" -eq 0
  assert_has_line "${STACKER_NAMESPACE}-add-resource-test-with-replacements-only: submitted (submitted for destruction)"
  assert_has_line "${STACKER_NAMESPACE}-add-resource-test-with-replacements-only: complete (stack destroyed)"
}

@test "stacker build - default mode, without & with protected stack" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: mystack
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    protected: ${PROTECTED}

EOF
  }

  config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: mystack
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2
  
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # First create the stack
  stacker build --interactive <(PROTECTED="false" config)
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-mystack: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-mystack: complete (creating new stack)"

  # Perform a additional resouce addition in interactive mode, non-protected stack
  stacker build --interactive <(config2) < <(echo "y")
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-mystack: submitted (updating existing stack)"
  assert_has_line "${STACKER_NAMESPACE}-mystack: complete (updating existing stack)"
  assert_has_line "Add Dummy2"

  # Perform another update, this time without interactive, but with a protected stack
  stacker build <(PROTECTED="true" config) < <(echo "y")
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-mystack: submitted (updating existing stack)"
  assert_has_line "${STACKER_NAMESPACE}-mystack: complete (updating existing stack)"
  assert_has_line "Remove Dummy2"

  # Cleanup
  stacker destroy --force <(config2)
  assert "$status" -eq 0
  assert_has_line "${STACKER_NAMESPACE}-mystack: submitted (submitted for destruction)"
  assert_has_line "${STACKER_NAMESPACE}-mystack: complete (stack destroyed)"
}

@test "stacker build - recreate failed stack, non-interactive mode" {
  needs_aws

  bad_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: recreate-failed
    class_path: stacker.tests.fixtures.mock_blueprints.Broken

EOF
  }

  good_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: recreate-failed
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy

EOF
  }

  teardown() {
    stacker destroy --force <(good_config)
  }

  stacker destroy --force <(good_config)

  # Create the initial stack. This must fail.
  stacker build <(bad_config)
  assert "$status" -eq 1
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed: submitted (rolling back new stack)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed: failed (rolled back new stack)"

  # Updating the stack should prompt to re-create it.
  stacker build --recreate-failed <(good_config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed: submitted (destroying stack for re-creation)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed: complete (creating new stack)"

  # Confirm the stack is really updated
  stacker build <(good_config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed: skipped (nochange)"

  # Cleanup
  stacker destroy --force <(good_config)
  assert "$status" -eq 0
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed: submitted (submitted for destruction)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed: complete (stack destroyed)"
}


@test "stacker build - recreate failed stack, interactive mode" {
  needs_aws

  bad_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: recreate-failed-interactive
    class_path: stacker.tests.fixtures.mock_blueprints.Broken

EOF
  }

  good_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: recreate-failed-interactive
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy

EOF
  }

  teardown() {
    stacker destroy --force <(good_config)
  }

  stacker destroy --force <(good_config)

  # Create the initial stack. This must fail.
  stacker build <(bad_config)
  assert "$status" -eq 1
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed-interactive: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed-interactive: submitted (rolling back new stack)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed-interactive: failed (rolled back new stack)"

  # Updating the stack should prompt to re-create it.
  stacker build -i <(good_config) <<< $'y\n'
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed-interactive: submitted (destroying stack for re-creation)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed-interactive: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed-interactive: complete (creating new stack)"

  # Confirm the stack is really updated
  stacker build -i <(good_config)
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed-interactive: skipped (nochange)"

  # Cleanup
  stacker destroy --force <(good_config)
  assert "$status" -eq 0
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed-interactive: submitted (submitted for destruction)"
  assert_has_line "${STACKER_NAMESPACE}-recreate-failed-interactive: complete (stack destroyed)"
}

@test "stacker build - handle rollbacks during updates" {
  needs_aws

  bad_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: update-rollback
    class_path: stacker.tests.fixtures.mock_blueprints.Broken

EOF
  }

  good_config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: update-rollback
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy

EOF
  }

  good_config2() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: update-rollback
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2

EOF
  }

  teardown() {
    stacker destroy --force <(good_config)
  }

  stacker destroy --force <(good_config)

  # Create the initial stack
  stacker build <(good_config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-update-rollback: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-update-rollback: complete (creating new stack)"

  # Do a bad update and watch the rollback
  stacker build <(bad_config)
  assert "$status" -eq 1
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-update-rollback: submitted (updating existing stack)"
  assert_has_line "${STACKER_NAMESPACE}-update-rollback: submitted (rolling back update)"
  assert_has_line "${STACKER_NAMESPACE}-update-rollback: failed (rolled back update)"

  # Do a good update so we know we've correctly waited for rollback
  stacker build <(good_config2)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-update-rollback: submitted (updating existing stack)"
  assert_has_line "${STACKER_NAMESPACE}-update-rollback: complete (updating existing stack)"
}


@test "stacker build - handle rollbacks in dependent stacks" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: dependent-rollback-parent
    class_path: stacker.tests.fixtures.mock_blueprints.Broken

  - name: dependent-rollback-child
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    requires: [dependent-rollback-parent]

EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  stacker destroy --force <(config)

  # Verify both stacks fail during creation
  stacker build <(config)
  assert "$status" -eq 1
  assert_has_line "Using default AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-dependent-rollback-parent: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-dependent-rollback-parent: submitted (rolling back new stack)"
  assert_has_line "${STACKER_NAMESPACE}-dependent-rollback-parent: failed (rolled back new stack)"
  assert_has_line "${STACKER_NAMESPACE}-dependent-rollback-child: failed (dependency has failed)"
  assert_has_line "The following stacks failed: dependent-rollback-parent, dependent-rollback-child"
}

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
  assert_has_line "${STACKER_NAMESPACE}-vpc: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-vpc: complete (creating new stack)"

  # Perform a noop update to the stacks, in interactive mode.
  stacker build -i <(config)
  assert "$status" -eq 0
  assert_has_line "Using interactive AWS provider mode"
  assert_has_line "${STACKER_NAMESPACE}-vpc: skipped (nochange)"

  # Cleanup
  stacker destroy --force <(config)
  assert "$status" -eq 0
  assert_has_line "${STACKER_NAMESPACE}-vpc: submitted (submitted for destruction)"
  assert_has_line "${STACKER_NAMESPACE}-vpc: complete (stack destroyed)"
}

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

@test "stacker build - no parallelism" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc1
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: vpc2
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build -j 1 <(config)
  assert "$status" -eq 0
  assert_has_line "${STACKER_NAMESPACE}-vpc1: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-vpc1: complete (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-vpc2: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-vpc2: complete (creating new stack)"
}

@test "stacker build - tailing" {
  needs_aws

  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: bastion
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    requires: [vpc]
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  # Create the new stacks.
  stacker build --tail <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_line "Tailing stack: ${STACKER_NAMESPACE}-vpc"
  assert_has_line "${STACKER_NAMESPACE}-vpc: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-vpc: complete (creating new stack)"
  assert_has_line "Tailing stack: ${STACKER_NAMESPACE}-bastion"
  assert_has_line "${STACKER_NAMESPACE}-bastion: submitted (creating new stack)"
  assert_has_line "${STACKER_NAMESPACE}-bastion: complete (creating new stack)"
}
