#!/usr/bin/env bats

# This test will exercise the integration of hooks among the execution of stacks
# making use of the fact that S3 buckets cannot be deleted when not empty.
# The test will create the bucket and populate it during build, and erase the
# objects before destruction. If the hooks are not executed in the proper order,
# the destruction will fail, and so will the tst.

load ../test_helper

@test "stacker build - integrated hooks" {
  needs_aws

  config() {
    echo "namespace: ${STACKER_NAMESPACE}-integrated-hooks"
    cat <<'EOF'
stacks:
  - name: bucket
    profile: stacker
    template_path: fixtures/blueprints/bucket.yaml.j2
    variables:
      BucketName: "stacker-${envvar STACKER_NAMESPACE}-integrated-hooks-${awsparam AccountId}"

build_hooks:
  - name: write-hello
    path: stacker.hooks.command.run_command
    args:
      command: 'echo "Hello from Stacker!" > /tmp/hello.txt'
      shell: true

  - name: send-hello
    path: stacker.hooks.command.run_command
    requires:
      - write-hello
    args:
      command: 'aws s3 cp /tmp/hello.txt "s3://$BUCKET/hello.txt"'
      shell: true
      env:
        BUCKET: "${output bucket::BucketName}"
        AWS_PROFILE: stacker

  - name: send-world
    path: stacker.hooks.command.run_command
    requires:
      - send-hello
    args:
      command: 'aws s3 cp "s3://$BUCKET/hello.txt" "s3://$BUCKET/world.txt"'
      shell: true
      env:
        BUCKET: "${output bucket::BucketName}"
        AWS_PROFILE: stacker

destroy_hooks:
  - name: remove-world
    path: stacker.hooks.command.run_command
    args:
      command: 'aws s3 rm "s3://$BUCKET/world.txt"'
      shell: true
      env:
        BUCKET: "${output bucket::BucketName}"
        AWS_PROFILE: stacker

  - name: remove-hello
    path: stacker.hooks.command.run_command
    required_by:
      - remove-world
    args:
      command: 'aws s3 rm "s3://$BUCKET/hello.txt"'
      shell: true
      env:
        BUCKET: "${output bucket::BucketName}"
        AWS_PROFILE: stacker

  - name: clean-hello
    path: stacker.hooks.command.run_command
    required_by:
      - bucket
    args:
      command: [rm, -f, /tmp/hello.txt]
EOF
  }

  teardown() {
    stacker destroy --force <(config)
  }

  stacker build -t --recreate-failed <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_lines_in_order -E <<'EOF'
pre_build_hooks: complete
write-hello: complete
bucket: submitted \(creating new stack\)
bucket: complete \(creating new stack\)
upload: [^ ]*/hello.txt to s3://[^ ]*/hello.txt
send-hello: complete
copy: s3://[^ ]*/hello.txt to s3://[^ ]*/world.txt
send-world: complete
post_build_hooks: complete
EOF

  stacker destroy --force <(config)
  assert "$status" -eq 0
  assert_has_line "Using default AWS provider mode"
  assert_has_lines_in_order -E <<'EOF'
pre_destroy_hooks: complete
delete: s3://[^ ]*/world.txt
remove-world: complete
delete: s3://[^ ]*/hello.txt
remove-hello: complete
bucket: submitted \(submitted for destruction\)
bucket: complete \(stack destroyed\)
clean-hello: complete
post_destroy_hooks: complete
EOF
  assert ! -e /tmp/hello.txt

  # Check that hooks that use lookups from stacks that do not exist anymore are
  # not run
  stacker destroy --force <(config)
  assert "$status" -eq 0
  assert_has_lines_in_order <<'EOF'
pre_destroy_hooks: complete
remove-world: skipped
remove-hello: skipped
bucket: skipped
clean-hello: complete
post_destroy_hooks: complete
EOF
}
