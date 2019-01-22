## Upcoming release

## 1.6.0 (2019-01-21)

- New lookup format/syntax, making it more generic [GH-665]
- Allow lowercase y/Y when prompted [GH-674]
- Local package sources [GH-677]
- Add `in_progress` option to stack config [GH-678]
- Use default ACL for uploaded lambda code [GH-682]
- Display rollback reason after error [GH-687]
- ssm parameter types [GH-692]

## 1.5.0 (2018-10-14)

The big feature in this release is the introduction of "targets" which act as
sort of "virtual nodes" in the graph. It provides a nice way to logically group
stacks.

- Add support for "targets" [GH-572]
- Fix non-interactive changeset updates w/ stack policies [GH-657]
- Fix interactive_update_stack calls with empty string parameters [GH-658]
- Fix KMS unicode lookup in python 2 [GH-659]
- Locked stacks have no dependencies [GH-661]
- Set default profile earlier [GH-662]
- Get rid of recursion for tail retries and extend retry/timeout [GH-663]

## 1.4.1 (2018-08-28)

This is a minor bugfix release for 1.4.0, no major feature updates.

As of this release python 3.5+ support is no longer considered experimental, and should be stable.

Special thanks to @troyready for this release, I think most of these PRs were his :)

- allow raw cfn templates to be loaded from remote package\_sources [GH-638]
- Add missing config keys to s3 package source model [GH-642]
- Account for UsePreviousValue parameters in diff [GH-644]
- fix file lookup documented and actual return types [GH-646]
- Creates a memoized provider builder for AWS [GH-648]
- update git ref to explicitly return string (fix py3 bytes error) [GH-649]
- Lock botocore/boto to versions that work with moto [GH-651]

## 1.4.0 (2018-08-05)

- YAML & JSON codecs for `file` lookup [GH-537]
- Arbitrary `command` hook [GH-565]
- Fix datetime is not JSON serializable error [GH-591]
- Run dump and outline actions offline [GH-594]
- Helper Makefile for functional tests [GH-597]
- Python3 support!!! [GH-600]
- YAML blueprint testing framework [GH-606]
- new `add_output` helper on Blueprint [GH-611]
- Include lookup contents when lookups fail [GH-614]
- Fix issue with using previous value for parameters [GH-615]
- Stricter config parsing - only allow unrecognized config variables at the top-level [GH-623]
- Documentation for the `default` lookup [GH-636]
- Allow configs without stacks [GH-640]

## 1.3.0 (2018-05-03)

- Support for provisioning stacks in multiple accounts and regions has been added [GH-553], [GH-551]
- Added a `--profile` flag, which can be used to set the global default profile that stacker will use (similar to `AWS_PROFILE`) [GH-563]
- `class_path`/`template_path` are no longer required when a stack is `locked` [GH-557]
- Support for setting stack policies on stacks has been added [GH-570]

## 1.2.0 (2018-03-01)

The biggest change in this release has to do with how we build the graph
of dependencies between stacks. This is now a true DAG.  As well, to
speed up performance we now walk the graph in a threaded mode, allowing
true parallelism and speeding up "wide" stack graphs considerably.

- assertRenderedBlueprint always dumps current results [GH-528]
- The `--stacks` flag now automatically builds dependencies of the given stack [GH-523]
- an unecessary DescribeStacks network call was removed [GH-529]
- support stack json/yaml templates [GH-530]
- `stacker {build,destroy}` now executes stacks in parallel. Parallelism can be controled with a `-j` flag. [GH-531]
- logging output has been simplified and no longer uses ANSI escape sequences to clear the screen [GH-532]
- logging output is now colorized in `--interactive` mode if the terminal has a TTY [GH-532]
- removed the upper bound on the boto3 dependency [GH-542]

## 1.2.0rc2 (2018-02-27)

- Fix parameter handling for diffs [GH-540]
- Fix an issue where SIGTERM/SIGINT weren't handled immediately [GH-543]
- Log a line when SIGINT/SIGTERM are handled [GH-543]
- Log failed steps at the end of plan execution [GH-543]
- Remove upper bound on boto3 dependency [GH-542]

## 1.2.0rc1 (2018-02-15)

The biggest change in this release has to do with how we build the graph
of dependencies between stacks. This is now a true DAG.  As well, to
speed up performance we now walk the graph in a threaded mode, allowing
true parallelism and speeding up "wide" stack graphs considerably.

- assertRenderedBlueprint always dumps current results [GH-528]
- stacker now builds a DAG internally [GH-523]
- The `--stacks` flag now automatically builds dependencies of the given stack [GH-523]
- an unecessary DescribeStacks network call was removed [GH-529]
- support stack json/yaml templates [GH-530]
- `stacker {build,destroy}` now executes stacks in parallel. Parallelism can be controled with a `-j` flag. [GH-531]
- logging output has been simplified and no longer uses ANSI escape sequences to clear the screen [GH-532]
- logging output is now colorized in `--interactive` mode if the terminal has a TTY [GH-532]


## 1.1.4 (2018-01-26)

- Add `blueprint.to_json` for standalone rendering [GH-459]
- Add global config for troposphere template indent [GH-505]
- Add serverless transform/CREATE changeset types [GH-517]

## 1.1.3 (2017-12-23)

Bugfix release- primarily to deal with a bug that's been around since the
introduction of interactive mode/changesets. The bug primarily deals with the
fact that we weren't deleting Changesets that were not submitted. This didn't
affect anyone for the longest time, but recently people have started to hit
limits on the # of changesets in an account. The current thinking is that the
limits weren't enforced before, and only recently has been enforced.

- Add S3 remote package sources [GH-487]
- Make blueprint dump always create intermediate directories [GH-499]
- Allow duplicate keys for most config mappings except `stacks` [GH-507]
- Remove un-submitted changesets [GH-513]

## 1.1.2 (2017-11-01)

This is a minor update to help deal with some of the issues between `stacker`
and `stacker_blueprints` both having dependencies on `troposphere`. It loosens
the dependencies, allowing stacker to work with any reasonably new version
of troposphere (anything greater than `1.9.0`). `stacker_blueprints` will
likely require newer versions of troposphere, as new types are introduced to
the blueprints, but it's unlikely we'll change the `troposphere` version string
for stacker, since it relies on only the most basic parts of the `troposphere`
API.

## 1.1.1 (2017-10-11)

This release is mostly about updating the dependencies for stacker to newer
versions, since that was missed in the last release.

## 1.1.0 (2017-10-08)

- `--max-zones` removed from CLI [GH-427]
- Ami lookup: add region specification [GH-433]
- DynamoDB Lookup [GH-434]
- Environment file is optional now [GH-436]
- New functional test suite [GH-439]
- Structure config object using Schematics [GH-443]
- S3 endpoint fallback [GH-445]
- Stack specific tags [GH-450]
- Allow disabling of stacker bucket (direct CF updates) [GH-451]
- Uniform deprecation warnings [GH-452]
- Remote configuration support [GH-458]
- TroposphereType updates [GH-462]
- Fix replacements-only issue [GH-464]
- testutil enhancments to blueprint testing [GH-467]
- Removal of Interactive Provider (now combined w/ default provider) [GH-469]
- protected stacks [GH-472]
- MUCH Better handling of stack rollbacks & recreations [GH-473]
- follow\_symlinks argument for aws lambda hook [GH-474]
- Enable service\_role for cloudformation operations [GH-476]
- Allow setting stack description from config [GH-477]
- Move S3 templates into sub-directories [GH-478]

## 1.0.4 (2017-07-07)

- Fix issue w/ tail being required (but not existing) on diff/info/etc [GH-429]

## 1.0.3 (2017-07-06)

There was some reworking on how regions are handled, specifically around
s3 and where the buckets for both stacker and the awslambda lookup are created.
Now the stacker bucket will default to being created in the region where the
stacks are being created (ie: from the `--region` argument). If you want to
have the bucket be in a different region you now can set the
`stacker_bucket_region` top level config value.

For the awslambda hook, you also have the option of using `bucket_region` as
an argument, provided you are using a custom `bucket` for the hook. If you
are not using a custom bucket, then it will use the logic used above.

- add ami lookup [GH-360]
- Add support for Property objects in TroposphereType variables [GH-379]
- Add debugging statements to sys.path appending [GH-385]
- Catch undefined variable value [GH-388]
- Exponential backoff waiting for AWS changeset to stabilize [GH-389]
- Add parameter changes to diff output [GH-394]
- Add CODE\_OF\_CONDUCT.md [GH-399]
- Add a hint for forbidden bucket access [GH-401]
- Fix issues w/ "none" as variable values [GH-405]
- Remove extra '/' in blueprint tests [GH-409]
- Fix dump provider interaction with lookups [GH-410]
- Add ssmstore lookup docs [GH-411]
- Fix issue w/ s3 buckets in different regions [GH-413, GH-417]
- Disable loop logger whe --tail is provided [GH-414]
- Add envvar lookup [GH-418]

## 1.0.2 (2017-05-10)

- fix lambda hook determinism [GH-372]
- give lambda hook ability to upload to a prefix [GH-376]
- fix bad argument for approval in interactive provider [GH-381]

## 1.0.1 (2017-04-24)

- rxref lookup [GH-328]
- Cleaned up raise statement in blueprints [GH-348]
- Fix missing default provider for build\_parameters [GH-353]
- Setup codecov [GH-354]
- Added blueprint testing harness [GH-362]
- context hook\_data lookup [GH-366]

## 1.0.0 (2017-03-04)

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
- Add troposphere types [GH-257]
- change capabilities to CAPABILITY\_NAMED\_IAM [GH-262]
- Disable transformation of variables [GH-266]
- Support destroying a subset of stacks [GH-278]
- Update all hooks to use advanced results [GH-285]
- Use sys\_path for hooks and lookups [GH-286]
- Remove last of botocore connections [GH-287]
- Remove --var flag [GH-289]
- Avoid dictionary sharing pollution [GH-293]
- Change aws\_lambda hook handler to use proper parameters [GH-297]
- New `split` lookup handler [GH-302]
- add parse\_user\_data [GH-306]
- Add credential caching [GH-307]
- Require explicit call to `output` lookup [GH-310]
- Convert booleans to strings for CFNTypes [GH-311]
- Add ssmstore as a lookup type [GH-314]
- Added region to the ssm store test client [GH-316]
- Add default lookup [GH-317]
- Clean up errors from variables [GH-319]

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
