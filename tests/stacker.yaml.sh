#!/bin/bash

cat - <<EOF
namespace: ${STACKER_NAMESPACE}
stacks:
  - name: stackerFunctionalTests
    class_path: stacker.tests.fixtures.mock_blueprints.FunctionalTests
    variables:
      StackerBucket: stacker-${STACKER_NAMESPACE}
      StackerNamespace: ${STACKER_NAMESPACE}
EOF
