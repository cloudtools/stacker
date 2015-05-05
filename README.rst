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

Example
=======

We've provided an example stack in *conf/example.yaml* that can be launched
in your account.  It creates 4 stacks:

- A VPC (including NAT hosts in each AZ)
- A bastion stack (for ssh'ing into other stacks on the VPC)
- A RDS stack (postgres)
- An autoscaling group stack

The size of most of these is m3.medium, but you can change that in the config
if you'd like to play with something smaller. To launch the stacks, after
installing stacker and loading your AWS API keys in your environment
(AWS\_ACCESS\_KEY\_ID & AWS\_SECRET\_ACCESS\_KEY), call the following::

    stacker -v -p BaseDomain=example.com -r us-east-1 -p AZCount=2 -p CidrBlock=10.128.0.0/16 example.com conf/example.yaml

Here's the syntax help from the command::

  # stacker -h
  usage: stacker [-h] [-r REGION] [-m MAX_ZONES] [-v] [-p PARAMETER=VALUE]
                 [--stacks STACKNAME]
                 namespace config

  Launches or updates cloudformation stacks based on the given config. The
  script is smart enough to figure out if anything (the template, or parameters)
  has changed for a given stack. If not, it will skip that stack. Can also pull
  parameters from other stack's outputs.

  positional arguments:
    namespace             The namespace for the stack collection. This will be
                          used as the prefix to the cloudformation stacks as
                          well as the s3 bucket where templates are stored.
    config                The config file where stack configuration is located.
                          Must be in yaml format.

  optional arguments:
    -h, --help            show this help message and exit
    -r REGION, --region REGION
                          The AWS region to launch in. Default: us-east-1
    -m MAX_ZONES, --max-zones MAX_ZONES
                          Gives you the ability to limit the # of zones that
                          resources will be launched in. If not given, then
                          resources will be launched in all available
                          availability zones.
    -v, --verbose         Increase output verbosity. May be specified up to
                          twice.
    -p PARAMETER=VALUE, --parameter PARAMETER=VALUE
                          Adds parameters from the command line that can be used
                          inside any of the stacks being built. Can be specified
                          more than once.
    --stacks STACKNAME    Only work on the stacks given. Can be specified more
                          than once. If not specified then stacker will work on
                          all stacks in the config file.

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
use ``-p CidrBlock`` on the command line, it doesn't matter what is in the
config file or any existing stacks. This is useful if, for example, you want
to keep sensitive information (passwords, etc) out of the config file (which
you'll likely check into a RCS), but need a way to supply them.

When updating an existing stack, if you don't supply a parameter in either the
config or CLI, it will fall back on checking the existing stack for the
parameter. If it finds it, it will use that automatically.

.. _Remind: http://www.remind.com/
.. _troposphere: https://github.com/cloudtools/troposphere
