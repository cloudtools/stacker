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
  echo "$output" | grep -q "$@"
}

assert_has_lines_in_order() {
  local search_line
  read -r search_line || return $?

  for line in "${lines[@]}"; do
    if grep -q "$@" "$search_line" <<< "$line"; then
      if ! read -r search_line && [ -z "$search_line" ]; then
        return 0
      fi
    fi
  done

  echo "Error: did not match line in correct order: '$search_line'" >&2
  return 1
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
