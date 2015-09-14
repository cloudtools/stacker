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
