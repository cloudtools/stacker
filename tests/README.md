This directory contains the functional testing suite for stacker. It exercises all of stacker against a real AWS account.

## Setup

1. First, ensure that you're inside a virtualenv:

  ```console
  $ source venv/bin/activate
  ```
2. Set a stacker namespace & the AWS region for the test suite to use:

  ```console
  $ export STACKER_NAMESPACE=my-stacker-test-namespace
  ```
3. Generate an IAM user for the test suite to use:

  ```console
  $ ./stacker.yaml.sh | stacker build -
  ```
4. Grab the generated key pair for the user and set it in your shell:

  ```console
  $ ./stacker.yaml.sh | stacker info -
  $ export AWS_ACCESS_KEY_ID=access-key
  $ export AWS_SECRET_ACCESS_KEY=secret-access-key
  $ export STACKER_ROLE=<FunctionalTestRole>
  ```
5. Run the test suite:

  ```console
  $ brew install bats
  $ bats .
  ```
