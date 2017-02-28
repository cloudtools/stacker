#!/bin/sh
export AWS_DEFAULT_REGION=us-east-1

get_abs_filename() {
  # $1 : relative filename
  echo "$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
}

env_file_path=$(get_abs_filename "tmp.env")
config_file_path=$(get_abs_filename "tmp.yaml")

time stacker build $env_file_path $config_file_path