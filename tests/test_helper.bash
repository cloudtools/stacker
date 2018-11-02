#!/usr/bin/env bash

# To make the tests run faster, we don't wait between calls to DescribeStacks
# to check on the status of Create/Update.
export STACKER_STACK_POLL_TIME=0

if [ -z "$STACKER_NAMESPACE" ]; then
  >&2 echo "To run these tests, you must set a STACKER_NAMESPACE environment variable"
  exit 1
fi

if [ -z "$STACKER_ROLE" ]; then
  >&2 echo "To run these tests, you must set a STACKER_ROLE environment variable"
  exit 1
fi

# Setup a base .aws/config that can be use to test stack configurations that
# require stacker to assume a role.
export AWS_CONFIG_DIR=$(mktemp -d)
export AWS_CONFIG_FILE="$AWS_CONFIG_DIR/config"

cat <<EOF > "$AWS_CONFIG_FILE"
[default]
region = us-east-1

[profile stacker]
region = us-east-1
role_arn = ${STACKER_ROLE}
credential_source = Environment
EOF

# Simple wrapper around the builtin bash `test` command.
assert() {
  builtin test "$@"
}

# Checks that the given line is in $output.
assert_has_line() {
  echo "$output" | grep "$@" 1>/dev/null
}

# run runs the command and captures it's output.
#
# See https://github.com/sstephenson/bats/blob/03608115df2071fff4eaaff1605768c275e5f81f/libexec/bats-exec-test#L50-L66
run() {
  local e E T oldIFS
  [[ ! "$-" =~ e ]] || e=1
  [[ ! "$-" =~ E ]] || E=1
  [[ ! "$-" =~ T ]] || T=1
  set +e
  set +E
  set +T
  output="$("$@" 2>&1)"
  status="$?"
  oldIFS=$IFS
  IFS=$'\n' lines=($output)
  [ -z "$e" ] || set -e
  [ -z "$E" ] || set -E
  [ -z "$T" ] || set -T
  IFS=$oldIFS
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
