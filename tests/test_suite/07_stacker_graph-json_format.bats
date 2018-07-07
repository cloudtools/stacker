#!/usr/bin/env bats

load ../test_helper

@test "stacker graph - json format" {
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
  stacker graph -f json <(config)
  assert "$status" -eq 0
  assert $(echo "$output" | grep -v "Using default" | python -c "import sys, json; data = json.loads(sys.stdin.read()); print(data['steps']['vpc']['deps'] == [] and data['steps']['bastion1']['deps'] == ['vpc'] and data['steps']['app2']['deps'] == ['bastion2'])") = 'True'
}
