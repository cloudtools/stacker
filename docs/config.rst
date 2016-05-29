=============
Configuration
=============

stacker makes use of a yaml formatted config file to define the different
cloudformation stacks that make up a given environment.

The configuration file has a loose definition, with only a few top-level
keywords. Other than those keywords, you can define your own top-level keys
to make use of other yaml features like `anchors & references`_ to avoid
duplicating config. (See `YAML anchors & references`_ for details)

Top Level Keywords
==================

Pre & Post Hooks
----------------

Many actions allow for pre & post hooks. These are python methods that are
executed before, and after the action is taken for the entire config. Only the
following actions allow pre/post hooks:

* build (keywords: *pre_build*, *post_build*)
* destroy (keywords: *pre_destroy*, *post_destroy*)

There are a few reasons to use these, though the most common is if you want
better control over the naming of a resource than what Cloudformation allows.

The keyword is a list of dictionaries with the following keys:

**path:**
  the python import path to the hook
**required:**
  whether to stop execution if the hook fails
**args:**
  a dictionary of arguments to pass to the hook

An example using the *create_domain* hook for creating a route53 domain before
the build action::

  pre_build:
    - path: stacker.hooks.route53.create_domain
      required: true
      args:
        domain: mydomain.com

Mappings
--------

Mappings are dictionaries that are provided as Mappings_ to each Cloudformation
stack that stacker produces.

These can be useful for providing things like different AMIs for different
instance types in different regions::

  mappings:
    AmiMap:
      us-east-1:
        NAT: ami-ad227cc4
        ubuntu1404: ami-74e27e1c
        bastion: ami-74e27e1c
      us-west-2:
        NAT: ami-290f4119
        ubuntu1404: ami-5189a661
        bastion: ami-5189a661

These can be used in each blueprint/stack as usual.


Stacks
------

This is the core part of the config - this is where you define each of the
stacks that will be deployed in the environment.  The stop level keyword
*stacks* is populated with a list of dictionaries, each representing a single
stack to be built.

A stack has the following keys:

**name:**
  The base name for the stack (note: the namespace from the environment
  will be prepended to this)
**class_path:**
  The python class path to the Blueprint to be used.
**parameters:**
  A dictionary of Parameters_ to pass into cloudformation when the
  stack is submitted.
**locked:**
  (optional) If set to true, the stack is locked and will not be
  updated unless the stack is passed to stacker via the *--force* flag.
  This is useful for *risky* stacks that you don't want to take the
  risk of allowing Cloudformation to update, but still want to make
  sure get launched when the environment is first created.
**enabled:**
  (optional) If set to false, the stack is disabled, and will not be
  built or updated. This can allow you to disable stacks in different
  environments.

Here's an example from stacker_blueprints_, used to create a VPC::

  stacks:
    - name: vpc
      class_path: stacker_blueprints.vpc.VPC
      locked: false
      enabled: true
      parameters:
        InstanceType: m3.medium
        SshKeyName: default
        ImageName: NAT
        AZCount: 2
        PublicSubnets: 10.128.0.0/24,10.128.1.0/24,10.128.2.0/24,10.128.3.0/24
        PrivateSubnets: 10.128.8.0/22,10.128.12.0/22,10.128.16.0/22,10.128.20.0/22
        CidrBlock: 10.128.0.0/16


Parameters
==========

Parameters are a Cloudformation concept that allow you to re-use an existing
Cloudformation template, but modify its behavior by passing in different
values.

stacker tries to make working with Parameters a little easier in a few ways:

YAML anchors & references
-------------------------

If you have a common set of parameters that you need to pass around in many
places, it can be annoying to have to copy and paste them in multiple places.
Instead, using a feature of YAML known as `anchors & references`_, you can
define common values in a single place and then refer to them with a simple
syntax.

For example, say you pass a common domain name to each of your stacks, each of
them taking it as a Parameter. Rather than having to enter the domain into 
each stack (and hopefully not typo'ing any of them) you could do the
following::

  domain_name: mydomain.com &domain

Now you have an anchor called **domain** that you can use in place of any value
in the config to provide the value **mydomain.com**. You use the anchor with
a reference::

  stacks:
    - name: vpc
      class_path: stacker_blueprints.vpc.VPC
      parameters:
        DomainName: *domain

Even more powerful is the ability to anchor entire dictionaries, and then
reference them in another dictionary, effectively providing it with default
values.  For example::

  common_parameters: &common_parameters
    DomainName: mydomain.com
    InstanceType: m3.medium
    AMI: ami-12345abc

Now, rather than having to provide each of those Parameters to every stack that
could use them, you can just do this instead::

  stacks:
    - name: vpc
      class_path: stacker_blueprints.vpc.VPC
      parameters:
        << : *common_parameters
        InstanceType: c4.xlarge # override the InstanceType in this stack

Using Outputs as Parameters
---------------------------

Since stacker encourages the breaking up of your Cloudformation stacks into
entirely separate stacks, sometimes you'll need to pass values from one stack
to another. The way this is handled in stacker (and in most of Cloudformation)
is by having one stack provide Outputs_ for all the values that another
stack may need, and then using those as the inputs for another stacks
Parameters_. stacker makes this easier for you by providing a syntax for
Parameters_ that will cause stacker to automatically look up the values of
Outputs_ from another stack in its config. To do so, use the following format
for the Parameter on the target stack::

  MyParameter: OtherStack::OutputName

This example is taken from stacker_blueprints_ example config - when building
things inside a VPC, you will need to pass the *VpcId* of the VPC that you
want the resources to be located in.  If the *vpc* stack provides an Output
called *VpcId*, you can reference it easily::

  domain_name: my_domain &domain

  stacks:
    - name: vpc
      class_path: stacker_blueprints.vpc.VPC
      parameters:
        DomainName: *domain
    - name: webservers
      class_path: stacker_blueprints.asg.AutoscalingGroup
      parameters:
        DomainName: *domain
        VpcId: vpc::VpcId # gets the VpcId Output from the vpc stack

Note: Doing this creates an implicit dependency from the *webservers* stack
to the *vpc* stack, which will cause stacker to submit the *vpc* stack, and
then wait until it is complete until it submits the *webservers* stack.

Environments
------------

A pretty common use case is to have separate environments that you want to
look mostly the same, though with some slight modifications. For example, you
might want a *production* and a *staging* environment. The production
environment likely needs more instances, and often those instances will be
of a larger instance type. Environments allow you to use your existing
stacker config, but provide different values based on the environment file
chosen on the command line. For more information, see the
`Environments <environments.rst>`_ documentation.


.. _`anchors & references`: https://en.wikipedia.org/wiki/YAML#Repeated_nodes
.. _Mappings: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/mappings-section-structure.html
.. _Outputs: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/outputs-section-structure.html
.. _stacker_blueprints: https://github.com/remind101/stacker_blueprints
