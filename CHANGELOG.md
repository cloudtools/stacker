## 1.0.0a5 (2016-11-28)

This is a major release with the main change being the removal of the old
Parameters logic in favor of Blueprint Variables and Lookups.

- Add support for resolving variables when calling `dump`[GH-231]
- Remove old Parameters code [GH-232]
- Pass Context & Provider to hooks [GH-233]
- Fix Issue w/ Dump [GH-241]
- Support `allowed_values` within variable definitions [GH-245]
- Fix filehandler lookups with pseudo parameters [GH-247]
- keypair hook update to match route53 update [GH-248]
- Add support for `TroposphereType` [GH-249]
- Allow = in lookup contents [GH-251]
- change capabilities to CAPABILITY\_NAMED\_IAM [GH-262]

## 0.8.6 (2017-01-26)

- Support destroying subset of stacks [GH-278]
- Update all hooks to use advanced results [GH-285]
- Use sys\_path for hooks and lookups [GH-286]
- Remove last of botocore conns [GH-287]
- Avoid dictionary sharing pollution [GH-293]

## 0.8.5 (2016-11-28)

- Allow `=` in lookup input [GH-251]
- Add hook for uploading AWS Lambda functions [GH-252]
- Upgrade hard coded capabilities to include named IAM [GH-262]
- Allow hooks to return results that can be looked up later [GH-270]

## 0.8.4 (2016-11-01)

- Fix an issue w/ boto3 version string not working with older setuptools

## 0.8.3 (2016-10-31)

- pass context to hooks as a kwarg [GH-234]
- Fix file handler lookups w/ pseudo parameters [GH-239]
- Allow use of later boto3 [GH-253]

## 0.8.1 (2016-09-22)

Minor update to remove dependencies on stacker\_blueprints for tests, since it
resulted in a circular dependency.  This is just a fix to get tests running again,
and results in no change in functionality.

## 0.8.0 (2016-09-22)

This is a big release which introduces the new concepts of Blueprint Variables
and Lookups. A lot of folks contributed to this release - in both code, and just
testing of the new features.  Thanks to:

@kylev, @oliviervg1, @datadotworld, @acmcelwee, @troyready, @danielkza, and @ttarhan

Special thanks to @mhahn who did the bulk of the heavy lifting in this release, and
the work towards 1.0!

- Add docs on config, environments & translators [GH-157]
- locked output changed to debug [GH-159]
- Multi-output parameter doc [GH-160]
- Remove spaces from multi-item parameters [GH-161]
- Remove blueprints & configs in favor of stacker\_blueprints [GH-163]
- Clean up plan/status split [GH-165]
- Allow s3 server side encryption [GH-167]
- Support configurable namespace delimiter [GH-169]
- Support tags as a new top-level keyword [GH-171]
- Update to boto3 [GH-174]
- Interactive AWS Provider [GH-178]
- Add config option for appending to sys.path [GH-179]
- More condensed output [GH-182]
- File loading lookup [GH-185]
- Handle stacks without parameters [GH-193]
- Implement blueprint variables & lookups [GH-194]
- Fix traceback on interactive provider when adding resources [GH-198]
- kms lookup [GH-200]
- Compatible release version dependencies [GH-201]
- add xref lookup [GH-202]
- Update docstrings for consistency [GH-204]
- Add support for CFN Parameter types in Blueprint Variables [GH-206]
- Deal w/ multiprocessing library sharing ssl connections [GH-208]
- Fix issues with slashes inside variable lookups [GH-213]
- Custom validators for blueprint variables [GH-218]

## 0.6.3 (2016-05-24)
- add `stacker dump` subcommand for testing stack/blueprints [GH-156]

## 0.6.2 (2016-05-17)
- Allow users to override name of bucket to store templates [GH-145]
- Add support for passing environment variables on the cli via --env [GH-148]
- Cleanup output on non-verbose runs [GH-153]
- Added `compare_env` command, for easier comparing of environment files [GH-155]

## 0.6.1 (2016-02-11)
- Add support for the 'stacker diff' command [GH-133]
- Python boolean parameters automatically converted to strings for CloudFormation [GH-136]
- No longer require mappings in config [GH-140]
- Skipped steps now include a reason [GH-141]

## 0.6.0 (2016-01-07)

- Support tailing cloudformation event stream when building/destroying stacks [GH-90]
- More customizable ASG userdata & options [GH-100]
- Deprecate 'blueprints' in favor of 'stacker\_blueprints' package [GH-125]
- Add KMS based encryption translator [GH-126]
- Fix typo in ASG customization [GH-127]
- Allow file:// prefix with KMS encryption translator [GH-128]
- No longer require a confirmation if the user passes the `--force` flag when destroying [GH-131]

## 0.5.4 (2015-12-03)

- Fix memory leak issue (GH-111) [GH-114]
- Add enabled flag to stacks [GH-115]
- Add support for List<AWS::EC2::*> parameters [GH-117]
- Add eu-west-1 support for empire [GH-116]
- Move get\_fqn to a function, add tests [GH-119]
- Add new postgres versions (9.4.4, 9.4.5) [GH-121]
- Handle blank parameter values [GH-120]

## 0.5.3 (2015-11-03)

- Add --version [GH-91]
- Simplify environment file to key: value, rather than YAML [GH-94]
- Ensure certificate exists hook [GH-94]
- Ensure keypair exists hook [GH-99]
- Custom field constructors & vault encryption [GH-95]
- DBSnapshotIdentifier to RDS blueprints [GH-105]
- Empire ECS Agent telemetry support fixes, use new Empire AMI [GH-107]
- Remove stack tags [GH-110]

## 0.5.2 (2015-09-10)

- Add Dockerfile/image [GH-87]
- Clean up environment docs [GH-88]
- Make StorageType configurable in RDS v2 [GH-92]

## 0.5.1 (2015-09-08)

- Add info subcommand [GH-73]
- Move namespace into environment [GH-72]
- Simplified basecommand [GH-74]
- Documentation updates [GH-75, GH-77, GH-78]
- aws\_helper removal [GH-79]
- Move VPC to use LOCAL\_PARAMETERS [GH-81]
- Lower default AZ count to 2 [GH-82]
- Allow use of all parameter properties [GH-83]
- Parameter gathering in method [GH-84]
- NoEcho on sensitive parameters in blueprnts [GH-85]
- Version 2 RDS Blueprints [GH-86]

## 0.5.0 (2015-08-13)

- stacker subcommands [GH-35]
- Added Empire production stacks [GH-43]
  - Major change in internal code layout & added testing
- added destroy subcommand [GH-59]
- Local Blueprint Parameters [GH-61]
- Lockable stacks [GH-62]
- Deal with Cloudformation API throttling [GH-64]
- Clarify Remind's usage of stacker in README [GH-70]

## 0.4.1 (2015-07-23)

- Stack Specific Parameters [GH-32]
- Random fixes & cleanup [GH-34]
- Handle skipped rollbacks [GH-36]
- Internal zone detection [GH-39]
- Internal hostname conditional [GH-40]
- Empire production stacks [GH-43]

## 0.4.0 (2015-05-13)

- Optional internal DNS Zone on vpc blueprint [GH-29]
- Add environment concept [GH-27]
- Optional internal zone cname for rds databases [GH-30]

## 0.3.0 (2015-05-05)

- remove auto-subnet splitting in vpc stack (GH-25)
- create bucket in correct region (GH-17, GH-23)
- asg sets optionally sets up ELB w/ (optional) SSL
- Remove DNS core requirement, add plugin/hook system (GH-26)

## 0.2.2 (2015-03-31)

- Allow AWS to generate the DBInstanceIdentifier

## 0.2.1 (2015-03-31)
- Bah, typo in version string, fixing

## 0.2.0 (2015-03-31)

- New taxonomy (GH-18)
- better setup.py (GH-16) - thanks mhahn
- Use exitsing parameters (GH-20)
- Able to work on subset of stacks (GH-14)
- Config cleanup (GH-9)
