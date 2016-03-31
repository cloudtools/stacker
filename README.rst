=======
stacker
=======

About
=====

stacker is a tool and library used to create & update multiple CloudFormation
stacks. It was originally written at Remind_ and
released to the open source community.

stacker StackTemplates are written in troposphere_, though the purpose of
most templates is to keep them as generic as possible and then use
configuration (and CloudFormation Parameters/Outputs) to modify them.

At this point this is very much alpha software - it is still in heavy
development, and interfaces/configuration/etc may/will likely/most definitely
change :)

That said, at Remind we use stacker to manage all of our Cloudformation stacks-
both in development, staging and production without any major issues.

Stacker Command
===============

The stacker command is built to have sub-commands, much like git. Currently the
comands are:

- ``build`` which handles taking your stack config and then launching or
  updating stacks as necessary.
- ``destroy`` which tears down your stacks
- ``diff`` which compares your currently deployed stack templates to your
  config files
- ``info`` which prints information about your currently deployed stacks

Example
=======

We've provided an example stack in *conf/example.yaml* that can be launched
in your account.  It creates 4 stacks:

- A VPC (including NAT hosts in each AZ, and dns entries in *BaseDomain*)
- A public, route53 zone (*BaseDomain* parameter)
- A bastion stack (for ssh'ing into other stacks on the VPC)
- A RDS stack (postgres)
- An autoscaling group stack

The size of most of these is m3.medium, but you can change that in the config
if you'd like to play with something smaller. To launch the stacks, after
installing stacker and loading your AWS API keys in your environment
(AWS\_ACCESS\_KEY\_ID & AWS\_SECRET\_ACCESS\_KEY), call the following::

    stacker build -v -p BaseDomain=blahblah.com -r us-east-1 conf/stage.env conf/example.yaml

As of now there is no option to tear down the stack in the tool (we plan to
add it), so you'll need to tear the stacks it creates down manually. When doing
so, it's important that you tear down all the stacks BUT the VPC stack first,
since they all depend on the VPC stack. Once they are torn down, you can safely
tear down the VPC stack. If you try deleting them all (including VPC) in one
swoop, you'll see that VPC stack gets hung up while waiting for the others to
tear down.

Defining Parameters
===================

There are multiple ways to define parameters for stacks, each useful in
different ways:

- the ``-p/--parameter`` command line argument
- in the stack config
- from an existing stack

Each of those overrides similarly named parameters beneath it, so if you
use ``-p CidrBlock=`` on the command line, it doesn't matter what is in the
config file or any existing stacks. This is useful if, for example, you want
to keep sensitive information (passwords, etc) out of the config file (which
you'll likely check into a RCS), but need a way to supply them.

When updating an existing stack, if you don't supply a parameter in either the
config or CLI, it will fall back on checking the existing stack for the
parameter. If it finds it, it will use that automatically.

One additional bit of functionality that should be noted is that if a Parameter
is defined, but has no value, for example in the stack config like this::

    MyParameter:

That parameter will not be submitted to the stack. This allows you to control
whether a parameter is submitted to a stack by using environments.

Environments
============

As well as defining the stack config, you'll need to specify an
environment. The environment should point to a yaml formatted file that
contains a flat dictionary (ie: only ``key: value`` pairs).  Those keys
can be used in the stack config as python `string.Template`_ mappings.

For example, if you wanted to name a stack based on the environment you were
building it in, first you would create an environment file with the
environment name in it (staging in this case)::

  environment: stage

Then, in the stack definition for the stack you are modifying (say the vpc
stack), you would have the following::

  - name: ${environment}VPC

Stacker would then name the VPC stack ``stageVPC``.

At a minimum the environment must define the ``namespace`` parameter::

  namespace: example.com

The namespace should be a unique name that the stacks will be built under.
This value will be used to prefix the CloudFormation stack names as well
as the s3 bucket that contains the stacker templates. Specifying the
namespace in the environment file helps preserve the namespace for the
stacks between subsequent builds.

.. _Remind: http://www.remind.com/
.. _troposphere: https://github.com/cloudtools/troposphere
.. _string.Template: https://docs.python.org/2/library/string.html#template-strings

Overriding CloudFormation S3 bucket
===================================

Stacker uploads your CloudFormation templates to S3 prior to creating your
stacks. This is to get around limitations imposed by the CloudFormation API. By
default all templates are uploaded to a ``stacker-${namespace}`` bucket in your
AWS account, where ``namespace`` is the one that you defined in your
environment.

You can override where Stacker uploads your template by specifying the
following in your stack configuration file::

  stacker_bucket: my-bucket


Translators
===========

Stacker provides the ability to dynamically replace values in the config via a
concept called translators. A translator is meant to take a value and convert
it by calling out to another service or system. This is initially meant to
deal with encrypting fields in your config.

Translators are custom YAML constructors. As an example, if you have a
database and it has a parameter called ``DBPassword`` that you don't want to
store in clear text in your config (maybe because you want to check it into
your version control system to share with the team), you could instead
encrypt the value using ``kms``. For example::

  # We use the aws cli to get the encrypted value for the string
  # "PASSWORD" using the master key called 'myStackerKey' in us-east-1
  $ aws --region us-east-1 kms encrypt --key-id alias/myStackerKey \
      --plaintext "PASSWORD" --output text --query CiphertextBlob

  CiD6bC8t2Y<...encrypted blob...>

  # In stacker we would reference the encrypted value like:
  DBPassword: !kms us-east-1@CiD6bC8t2Y<...encrypted blob...>

  # The above would resolve to
  DBPassword: PASSWORD

This requires that the person using stacker has access to the master key used
to encrypt the value.

It is also possible to store the encrypted blob in a file (useful if the
value is large) using the `file://` prefix, ie::

  DockerConfig: !kms file://dockercfg

NOTE: Translators resolve the path specified with `file://` relative to
the location of the config file, not where the stacker command is run.

Docker
======

Stack can also be executed from Docker. Use this method to run stacker if you
want to avoid setting up a python environment::

  docker run -it -v `pwd`:/stacks remind101/stacker build ...
