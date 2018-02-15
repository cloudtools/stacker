#!/usr/bin/env bash

# To make the tests run faster, we don't wait between calls to DescribeStacks
# to check on the status of Create/Update.
export STACKER_STACK_POLL_TIME=0

if [ -z "$STACKER_NAMESPACE" ]; then
  >&2 echo "To run these tests, you must set a STACKER_NAMESPACE environment variable"
  exit 1
fi

# Simple wrapper around the builtin bash `test` command.
assert() {
  builtin test "$@"
}

# Checks that the given line is in $output.
assert_has_line() {
  echo "$output" | grep "$@" 1>/dev/null
}

# This helper wraps "stacker" with bats' "run" and also outputs debug
# information. If you need to execute the stacker binary _without_ calling
# "run", you can use "command stacker".
stacker() {
  echo "$ stacker $@"
  run command stacker "$@"
  echo "$output"
  echo
}

# A helper to tag a test as requiring access to AWS. If no credentials are set,
# then the tests will be skipped.
needs_aws() {
  if [ -z "$AWS_ACCESS_KEY_ID" ]; then
    skip "aws credentials not set"
  fi
}
