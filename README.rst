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

Stacker Command
===============

The stacker command is built to have sub-commands, much like git. Currently the
only implemented command is ``build``, which handles taking your stack config
and then launching or updating stacks as necessary.

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

    stacker build -v -p BaseDomain=blahblah.com -r us-east-1 example.com conf/example.yaml

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

Environments
============

As well as definining the stack config, you can further customize the stack
config via an environment (ie the ``-e or --environment`` argument).

The environment should point at a yaml formatted file that contains a flat
dictionary (ie: only key: value pairs).  Those keys can be used in the
stack config as python `string.Template`_ mappings.

For example, if you wanted to name a stack based on the environment you were
building it in, first you would create an environment file with the
environment name in it (staging in this case)::

  environment: stage

Then, in the stack definition for the stack you are modifying (say the vpc
stack), you would have the following::

  - name: ${environment}VPC

Stacker would then name the VPC stack ``stageVPC``.

.. _Remind: http://www.remind.com/
.. _troposphere: https://github.com/cloudtools/troposphere
.. _string.Template: https://docs.python.org/2/library/string.html#template-strings
