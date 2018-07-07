#!/usr/bin/env bats
#
load ../test_helper

@test "stacker build - empty config" {
  stacker build <(echo "")
  assert ! "$status" -eq 0
  assert_has_line 'Should have more than one element'
}
