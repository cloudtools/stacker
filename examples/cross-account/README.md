This is a secure example setup to support cross-account provisioning of stacks with stacker. It:

1. Sets up an appropriate [AWS Config File](https://docs.aws.amazon.com/cli/latest/topic/config-vars.html) in [.aws/config] for stacker to use, with profiles for a "master", "prod" and "stage" AWS account.
2. Configures a stacker bucket in the "master" account, with permissions that allows CloudFormation in "sub" accounts to fetch templates.

## Setup

### Create IAM roles

First things first, we need to create some IAM roles that stacker can assume to make changes in each AWS account. This is generally a manual step after you've created a new AWS account.

In each account, create a new stack using the [stacker-role.yaml](./templates/stacker-role.yaml) CloudFormation template. This will create an IAM role called `Stacker` in the target account, with a trust policy that will allow the `Stacker` role in the master account to `sts:AssumeRole` it.

Once the roles have been created, update the `role_arn`'s in [.aws/config] to match the ones that were just created.

```console
$ aws cloudformation describe-stacks \
  --profile <profile> \
  --stack-name <stack name> \
  --query 'Stacks[0].Outputs' --output text
StackerRole     arn:aws:iam::<account id>:role/Stacker
```

### GetSessionToken

In order for stacker to be able to call `sts:AssumeRole` with the roles we've specified in [.aws/config], we'll need to pass it credentials via environment variables (see [`credential_source = Environment`](./.aws/config)) with appropriate permissions. Generally, the best way to do this is to obtain temporary credentials via the `sts:GetSessionToken` API, while passing an MFA OTP.

Assuming you have an IAM user in your master account, you can get temporary credentials using the AWS CLI:

```console
$ aws sts get-session-token \
  --serial-number arn:aws:iam::<master account id>:mfa/<iam username> \
  --token-code <mfa otp>
```

At Remind, we like to use [aws-vault], which allows us to simplify this to:

```console
$ aws-vault exec default -- env
AWS_VAULT=default
AWS_DEFAULT_REGION=us-east-1
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=ASIAJ...ICSXSQ
AWS_SECRET_ACCESS_KEY=4oFx...LSNjpFq
AWS_SESSION_TOKEN=FQoDYXdzED...V6Wrdko2KjW1QU=
AWS_SECURITY_TOKEN=FQoDYXdzED...V6Wrdko2KjW1QU=
```

For the rest of this guide, I'll use `aws-vault` for simplicity.

**NOTE**: You'll need to ensure that this IAM user has access to call `sts:AssumeRole` on the `Stacker` IAM role in the "master" account.

### Bootstrap Stacker Bucket

After we have some IAM roles that stacker can assume, and some temporary credentials, we'll want to create a stacker bucket in the master account, and allow the Stacker roles in sub-accounts access to fetch templates from it.

To do that, first, change the "Roles" variable in [stacker.yaml], then:

```console
$ aws-vault exec default # GetSessionToken + MFA
$ AWS_CONFIG_FILE=.aws/config stacker build --profile master --stacks stacker-bucket stacker.yaml
```

Once the bucket has been created, replace `stacker_bucket` with the name of the bucket in [stacker.yaml].

```console
$ aws cloudformation describe-stacks \
  --profile master \
  --stack-name stacker-bucket \
  --query 'Stacks[0].Outputs' --output text
BucketId     stacker-bucket-1234
```

### Provision stacks

Now that everything is setup, you can add new stacks to your config file, and target them to a specific AWS account using the `profile` option. For example, if I wanted to create a new VPC in both the "production" and "staging" accounts:

```yaml
stacks:
  - name: prod/vpc
    stack_name: vpc
    class_path: stacker_blueprints.vpc.VPC
    profile: prod # target this to the production account
  - name: stage/vpc
    stack_name: vpc
    class_path: stacker_blueprints.vpc.VPC
    profile: stage # target this to the staging account
```

```console
$ AWS_CONFIG_FILE=.aws/config stacker build --profile master stacker.yaml
```

[.aws/config]: ./.aws/config
[stacker.yaml]: ./stacker.yaml
[aws-vault]: https://github.com/99designs/aws-vault
