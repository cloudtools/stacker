This directory contains the functional testing suite for stacker. It exercises all of stacker against a real AWS account. Make sure you have the AWS credentials loaded into your environment when you run these steps.

## Setup

1. First, ensure that you're inside a virtualenv:

  ```console
  $ source venv/bin/activate
  ```

2. Set a stacker namespace & the AWS region for the test suite to use:

  ```console
  $ export STACKER_NAMESPACE=my-stacker-test-namespace
  $ export AWS_DEFAULT_REGION=us-east-1
  ```

3. Ensure that bats is installed:

  ```console
  # On MacOS if brew is installed
  $ brew install bats-core
  ```

4. Setup functional test environment & run tests:

  ```console
  # To run all the tests
  $ make -C tests test
  # To run specific tests (ie: tests 1, 2 and 3)
  $ TESTS="1 2 3" make -C tests test
  ```
