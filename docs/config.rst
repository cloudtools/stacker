=============
Configuration
=============

stacker makes use of a YAML formatted config file to define the different
CloudFormation stacks that make up a given environment.

The configuration file has a loose definition, with only a few top-level
keywords. Other than those keywords, you can define your own top-level keys
to make use of other YAML features like `anchors & references`_ to avoid
duplicating config. (See `YAML anchors & references`_ for details)

Top Level Keywords
==================

Namespace Delimiter
-------------------

By default, stacker will use '-' as a delimiter between your namespace and the
declared stack name to build the actual CloudFormation stack name that gets
created. Since child resources of your stacks will, by default, use a portion
of your stack name in the auto-generated resource names, the first characters
of your fully-qualified stack name potentially convey valuable information to
someone glancing at resource names. If you prefer to not use a delimiter, you
can pass the **namespace_delimiter** top level key word in the config as an empty string.

See the `CloudFormation API Reference`_ for allowed stack name characters

.. _`CloudFormation API Reference`: http://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_CreateStack.html

S3 Bucket
---------

Stacker, by default, pushes your CloudFormation templates into an S3 bucket
and points CloudFormation at the template in that bucket when launching or
updating your stacks. By default it uses a bucket named
**stacker-${namespace}**, where the namespace is the namespace provided in the
`environment <environments.html>`_ file.

If you want to change this, provide the **stacker_bucket** top level key word
in the config.

Module Paths
----------------
When setting the ``classpath`` for blueprints/hooks, it is sometimes desirable to
load modules from outside the default ``sys.path`` (e.g., to include modules
inside the same repo as config files).

Adding a path (e.g. ``./``) to the **sys_path** top level key word will allow
modules from that path location to be used.

Pre & Post Hooks
----------------

Many actions allow for pre & post hooks. These are python methods that are
executed before, and after the action is taken for the entire config. Only the
following actions allow pre/post hooks:

* build (keywords: *pre_build*, *post_build*)
* destroy (keywords: *pre_destroy*, *post_destroy*)

There are a few reasons to use these, though the most common is if you want
better control over the naming of a resource than what CloudFormation allows.

The keyword is a list of dictionaries with the following keys:

**path:**
  the python import path to the hook
**data_key:**
  If set, and the hook returns data (a dictionary), the results will be stored
  in the context.hook_data with the data_key as it's key.
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

Tags
----

CloudFormation supports arbitrary key-value pair tags. All stack-level, including automatically created tags, are
propagated to resources that AWS CloudFormation supports. See `AWS Cloudformation Resource Tags Type`_ for more details.
If no tags are specified, the `stacker_namespace` tag is applied to your stack with the value of `namespace` as the
tag value.

If you prefer to apply a custom set of tags, specify the top-level keyword `tags` as a map. Example::

  tags:
    "hello": world
    "my_tag:with_colons_in_key": ${dynamic_tag_value_from_my_env}
    simple_tag: simple value

If you prefer to have no tags applied to your stacks (versus the default tags that stacker applies), specify an empty
map for the top-level keyword::

  tags: {}

.. _`AWS CloudFormation Resource Tags Type`: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-properties-resource-tags.html

Mappings
--------

Mappings are dictionaries that are provided as Mappings_ to each CloudFormation
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

Lookups
-------

Lookups allow you to create custom methods which take a value and are
resolved at build time. The resolved values are passed to the `Blueprints
<blueprints.html>`_ before it is rendered. For more information, see the
`Lookups <lookups.html>`_ documentation.

stacker provides some common `lookups <lookups.html>`_, but it is
sometimes useful to have your own custom lookup that doesn't get shipped
with stacker. You can register your own lookups by defining a `lookups`
key::

  lookups:
    custom: path.to.lookup.handler

The key name for the lookup will be used as the type name when registering
the lookup. The value should be the path to a valid lookup handler.

You can then use these within your config::

  conf_value: ${custom some-input-here}


Stacks
------

This is the core part of the config - this is where you define each of the
stacks that will be deployed in the environment.  The top level keyword
*stacks* is populated with a list of dictionaries, each representing a single
stack to be built.

A stack has the following keys:

**name:**
  The base name for the stack (note: the namespace from the environment
  will be prepended to this)
**class_path:**
  The python class path to the Blueprint to be used.
**parameters:**
  A dictionary of Parameters_ to pass into CloudFormation when the
  stack is submitted. (note: parameters will be deprecated in the future
  in favor of variables)
**variables:**
  A dictionary of Variables_ to pass into the Blueprint when rendering the
  CloudFormation template. Variables_ can be any valid YAML data
  structure.
**locked:**
  (optional) If set to true, the stack is locked and will not be
  updated unless the stack is passed to stacker via the *--force* flag.
  This is useful for *risky* stacks that you don't want to take the
  risk of allowing CloudFormation to update, but still want to make
  sure get launched when the environment is first created.
**enabled:**
  (optional) If set to false, the stack is disabled, and will not be
  built or updated. This can allow you to disable stacks in different
  environments.
**requires:**
  (optional) a list of other stacks this stack requires. This is for explicit
  dependencies - you do not need to set this if you refer to another stack in
  a Parameter, so this is rarely necessary.

Here's an example from stacker_blueprints_, used to create a VPC::

  stacks:
    - name: vpc-example
      class_path: stacker_blueprints.vpc.VPC
      locked: false
      enabled: true
      variables:
        InstanceType: t2.small
        SshKeyName: default
        ImageName: NAT
        AZCount: 2
        PublicSubnets:
          - 10.128.0.0/24
          - 10.128.1.0/24
          - 10.128.2.0/24
          - 10.128.3.0/24
        PrivateSubnets:
          - 10.128.8.0/22
          - 10.128.12.0/22
          - 10.128.16.0/22
          - 10.128.20.0/22
        CidrBlock: 10.128.0.0/16


Parameters
==========

.. note::
  Parameters have been deprecated in favor of Variables_ and will be
  removed in a future release.

Parameters are a CloudFormation concept that allow you to re-use an existing
CloudFormation template, but modify its behavior by passing in different
values.

stacker tries to make working with Parameters a little easier in a few ways:

Parameter YAML anchors & references
-----------------------------------

If you have a common set of parameters that you need to pass around in many
places, it can be annoying to have to copy and paste them in multiple places.
Instead, using a feature of YAML known as `anchors & references`_, you can
define common values in a single place and then refer to them with a simple
syntax.

For example, say you pass a common domain name to each of your stacks, each of
them taking it as a Parameter. Rather than having to enter the domain into
each stack (and hopefully not typo'ing any of them) you could do the
following::

  domain_name: &domain mydomain.com

Now you have an anchor called **domain** that you can use in place of any value
in the config to provide the value **mydomain.com**. You use the anchor with
a reference::

  stacks:
    - name: vpc
      class_path: stacker_blueprints.vpc.VPC
      variables:
        DomainName: *domain

Even more powerful is the ability to anchor entire dictionaries, and then
reference them in another dictionary, effectively providing it with default
values. For example::

  common_variables: &common_parameters
    DomainName: mydomain.com
    InstanceType: m3.medium
    AMI: ami-12345abc

Now, rather than having to provide each of those Parameters to every stack that
could use them, you can just do this instead::

  stacks:
    - name: vpc
      class_path: stacker_blueprints.vpc.VPC
      parameters:
        << : *common_variables
        InstanceType: c4.xlarge # override the InstanceType in this stack

Variables
==========

Variables are values that will be passed into a `Blueprint
<blueprints.html>`_ before it is
rendered. Variables can be any valid YAML data structure and can leverage
Lookups_ to expand values at build time.

The following concepts make working with variables within large templates
easier:

YAML anchors & references
-------------------------

If you have a common set of variables that you need to pass around in many
places, it can be annoying to have to copy and paste them in multiple places.
Instead, using a feature of YAML known as `anchors & references`_, you can
define common values in a single place and then refer to them with a simple
syntax.

For example, say you pass a common domain name to each of your stacks, each of
them taking it as a Variable. Rather than having to enter the domain into
each stack (and hopefully not typo'ing any of them) you could do the
following::

  domain_name: mydomain.com &domain

Now you have an anchor called **domain** that you can use in place of any value
in the config to provide the value **mydomain.com**. You use the anchor with
a reference::

  stacks:
    - name: vpc
      class_path: stacker_blueprints.vpc.VPC
      variables:
        DomainName: *domain

Even more powerful is the ability to anchor entire dictionaries, and then
reference them in another dictionary, effectively providing it with default
values. For example::

  common_variables: &common_parameters
    DomainName: mydomain.com
    InstanceType: m3.medium
    AMI: ami-12345abc

Now, rather than having to provide each of those variables to every stack that
could use them, you can just do this instead::

  stacks:
    - name: vpc
      class_path: stacker_blueprints.vpc.VPC
      variables:
        << : *common_variables
        InstanceType: c4.xlarge # override the InstanceType in this stack

Using Outputs as Variables
---------------------------

Since stacker encourages the breaking up of your CloudFormation stacks into
entirely separate stacks, sometimes you'll need to pass values from one stack
to another. The way this is handled in stacker is by having one stack
provide Outputs_ for all the values that another stack may need, and then
using those as the inputs for another stack's Variables_. stacker makes
this easier for you by providing a syntax for Variables_ that will cause
stacker to automatically look up the values of Outputs_ from another stack
in its config. To do so, use the following format for the Variable on the
target stack::

  MyParameter: ${output OtherStack::OutputName}

Since referencing Outputs_ from stacks is the most common use case,
`output` is the default lookup type. For more information see Lookups_.

This example is taken from stacker_blueprints_ example config - when building
things inside a VPC, you will need to pass the *VpcId* of the VPC that you
want the resources to be located in. If the *vpc* stack provides an Output
called *VpcId*, you can reference it easily::

  domain_name: my_domain &domain

  stacks:
    - name: vpc
      class_path: stacker_blueprints.vpc.VPC
      variables:
        DomainName: *domain
    - name: webservers
      class_path: stacker_blueprints.asg.AutoscalingGroup
      variables:
        DomainName: *domain
        VpcId: ${output vpc::VpcId} # gets the VpcId Output from the vpc stack

Note: Doing this creates an implicit dependency from the *webservers* stack
to the *vpc* stack, which will cause stacker to submit the *vpc* stack, and
then wait until it is complete until it submits the *webservers* stack.

Environments
============

A pretty common use case is to have separate environments that you want to
look mostly the same, though with some slight modifications. For example, you
might want a *production* and a *staging* environment. The production
environment likely needs more instances, and often those instances will be
of a larger instance type. Environments allow you to use your existing
stacker config, but provide different values based on the environment file
chosen on the command line. For more information, see the
`Environments <environments.html>`_ documentation.

Translators
===========

.. note::
  Translators have been deprecated in favor of Lookups_ and will be
  removed in a future release.

Translators allow you to create custom methods which take a value, then modify
it before passing it on to the stack. Currently this is used to allow you to
pass a KMS encrypted string as a Parameter, then have KMS decrypt it before
submitting it to CloudFormation. For more information, see the
`Translators <translators.html>`_ documentation.

.. _`anchors & references`: https://en.wikipedia.org/wiki/YAML#Repeated_nodes
.. _Mappings: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/mappings-section-structure.html
.. _Outputs: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/outputs-section-structure.html
.. _stacker_blueprints: https://github.com/remind101/stacker_blueprints
