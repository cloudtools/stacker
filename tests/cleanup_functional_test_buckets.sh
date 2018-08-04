#!/usr/bin/env bash

if [ -z "$AWS_ACCESS_KEY_ID" ]
then
    echo "AWS_ACCESS_KEY_ID not set, skipping bucket cleanup."
    exit 0
fi

sudo pip install awscli

ALL_BUT_LAST_6_BUCKETS=$(aws s3 ls | grep stacker-cloudtools-functional-tests- | sort -r | tail -n +7 | awk '{print $3}')

for bucket in ${ALL_BUT_LAST_6_BUCKETS}
do
    echo "## Deleting bucket: 's3://$bucket'"
    aws --region us-east-1 s3 rm --recursive s3://$bucket/
    aws --region us-east-1 s3 rb s3://$bucket
done
