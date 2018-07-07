#!/usr/bin/env bats

load ../test_helper

@test "stacker build - no config" {
  stacker build
  assert ! "$status" -eq 0
  assert_has_line -E "too few arguments|the following arguments are required: config"
}
