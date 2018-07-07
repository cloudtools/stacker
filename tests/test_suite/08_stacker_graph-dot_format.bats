#!/usr/bin/env bats

load ../test_helper

@test "stacker graph - dot format" {
  config() {
    cat <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: vpc
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
  - name: bastion1
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2
    variables:
      StringVariable: \${output vpc::DummyId}
  - name: bastion2
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    variables:
      StringVariable: \${output vpc::DummyId}
  - name: app1
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy2
    variables:
      StringVariable: \${output bastion1::DummyId}
  - name: app2
    class_path: stacker.tests.fixtures.mock_blueprints.Dummy
    variables:
      StringVariable: \${output bastion2::DummyId}
EOF
  }

  # Print the graph
  stacker graph -f dot <(config)
  assert "$status" -eq 0
  assert_has_line '"bastion1" -> "vpc";'
  assert_has_line '"bastion2" -> "vpc";'
  assert_has_line '"app1" -> "bastion1";'
  assert_has_line '"app2" -> "bastion2";'
  assert $(echo "$output" | grep -A 2 vpc | tail -n 2 | grep -c vpc) = '0'
}
