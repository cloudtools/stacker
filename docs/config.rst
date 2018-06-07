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

Namespace
---------

You can provide a **namespace** to create all stacks within. The namespace will
be used as a prefix for the name of any stack that stacker creates, and makes
it unnecessary to specify the fully qualified name of the stack in output
lookups.

In addition, this value will be used to create an S3 bucket that stacker will
use to upload and store all CloudFormation templates.

In general, this is paired with the concept of `Environments
<environments.html>`_ to create a namespace per environment::

  namespace: ${namespace}

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
**stacker-${namespace}**, where the namespace is the namespace provided the
config.

If you want to change this, provide the **stacker_bucket** top level key word
in the config.

The bucket will be created in the same region that the stacks will be launched
in.  If you want to change this, or if you already have an existing bucket
in a different region, you can set the **stacker_bucket_region** to
the region where you want to create the bucket.

**S3 Bucket location prior to 1.0.4:**
  There was a "bug" early on in stacker that created the s3 bucket in us-east-1,
  no matter what you specified as your --region. An issue came up leading us to
  believe this shouldn't be the expected behavior, so we fixed the behavior.
  If you executed a stacker build prior to V 1.0.4, your bucket for templates
  would already exist in us-east-1, requiring you to specify the
  **stacker_bucket_region** top level keyword.

.. note::
  Deprecation of fallback to legacy template bucket. We will first try
  the region you defined using the top level keyword under
  **stacker_bucket_region**, or what was specified in the --region flag.
  If that fails, we fallback to the us-east-1 region. The fallback to us-east-1
  will be removed in a future release resulting in the following botocore
  excpetion to be thrown:

  ``TemplateURL must reference a valid S3 object to which you have access.``

  To avoid this issue, specify the stacker_bucket_region top level keyword
  as described above. You can specify this keyword now to remove the
  deprecation warning.

If you want stacker to upload templates directly to CloudFormation, instead of
first uploading to S3, you can set **stacker_bucket** to an empty string.
However, note that template size is greatly limited when uploading directly.
See the `CloudFormation Limits Reference`_.

.. _`CloudFormation Limits Reference`: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cloudformation-limits.html

Module Paths
------------
When setting the ``classpath`` for blueprints/hooks, it is sometimes desirable to
load modules from outside the default ``sys.path`` (e.g., to include modules
inside the same repo as config files).

Adding a path (e.g. ``./``) to the **sys_path** top level key word will allow
modules from that path location to be used.

Service Role
------------

By default stacker doesn't specify a service role when executing changes to
CloudFormation stacks. If you would prefer that it do so, you can set
**service_role** to be the ARN of the service that stacker should use when
executing CloudFormation changes.

This is the equivalent of setting ``RoleARN`` on a call to the following
CloudFormation api calls: ``CreateStack``, ``UpdateStack``,
``CreateChangeSet``.

See the AWS documentation for `AWS CloudFormation Service Roles`_.

.. _`AWS CloudFormation Service Roles`: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html?icmpid=docs_cfn_console

Remote Packages
---------------
The **package_sources** top level keyword can be used to define remote
sources for blueprints (e.g., retrieving ``stacker_blueprints`` on github at
tag ``v1.0.2``).

The only required key for a git repository config is ``uri``, but ``branch``,
``tag``, & ``commit`` can also be specified::

    package_sources:
      git:
        - uri: git@github.com:acmecorp/stacker_blueprints.git
        - uri: git@github.com:remind101/stacker_blueprints.git
          tag: 1.0.0
          paths:
            - stacker_blueprints
        - uri: git@github.com:contoso/webapp.git
          branch: staging
        - uri: git@github.com:contoso/foo.git
          commit: 12345678

If no specific commit or tag is specified for a repo, the remote repository
will be checked for newer commits on every execution of Stacker.

For ``.tar.gz`` & ``zip`` archives on s3, specify a ``bucket`` & ``key``::

    package_sources:
      s3:
        - bucket: mystackers3bucket
          key: archives/blueprints-v1.zip
          paths:
            - stacker_blueprints
        - bucket: anothers3bucket
          key: public/public-blueprints-v2.tar.gz
          requester_pays: true
        - bucket: yetanothers3bucket
          key: sallys-blueprints-v1.tar.gz
          # use_latest defaults to true - will update local copy if the
          # last modified date on S3 changes
          use_latest: false

Use the ``paths`` option when subdirectories of the repo/archive should be
added to Stacker's ``sys.path``.

Cloned repos/archives will be cached between builds; the cache location defaults
to ~/.stacker but can be manually specified via the **stacker_cache_dir** top
level keyword.

Remote Configs
~~~~~~~~~~~~~~
Configuration yamls from remote configs can also be used by specifying a list
of ``configs`` in the repo to use::

    package_sources:
      git:
        - uri: git@github.com:acmecorp/stacker_blueprints.git
          configs:
            - vpc.yaml

In this example, the configuration in ``vpc.yaml`` will be merged into the
running current configuration, with the current configuration's values taking
priority over the values in ``vpc.yaml``.

Dictionary Stack Names & Hook Paths
:::::::::::::::::::::::::::::::::::
To allow remote configs to be selectively overriden, stack names & hook
paths can optionally be defined as dictionaries, e.g.::

  pre_build:
    my_route53_hook:
      path: stacker.hooks.route53.create_domain:
      required: true
      enabled: true
      args:
        domain: mydomain.com
  stacks:
    vpc-example:
      class_path: stacker_blueprints.vpc.VPC
      locked: false
      enabled: true
    bastion-example:
      class_path: stacker_blueprints.bastion.Bastion
      locked: false
      enabled: true

Pre & Post Hooks
----------------

Many actions allow for pre & post hooks. These are python methods that are
executed before, and after the action is taken for the entire config. Hooks 
can be enabled or disabled, per hook. Only the following actions allow
pre/post hooks:

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
**enabled:**
  whether to execute the hook every stacker run. Default: True. This is a bool
  that grants you the ability to execute a hook per environment when combined
  with a variable pulled from an environment file.
**args:**
  a dictionary of arguments to pass to the hook

An example using the *create_domain* hook for creating a route53 domain before
the build action::

  pre_build:
    - path: stacker.hooks.route53.create_domain
      required: true
      enabled: true
      args:
        domain: mydomain.com

An example of a hook using the ``create_domain_bool`` variable from the environment
file to determine if hook should run. Set ``create_domain_bool: true`` or
``create_domain_bool: false`` in the environment file to determine if the hook
should run in the environment stacker is running against::

  pre_build:
    - path: stacker.hooks.route53.create_domain
      required: true
      enabled: ${create_domain_bool}
      args:
        domain: mydomain.com

Tags
----

CloudFormation supports arbitrary key-value pair tags. All stack-level, including automatically created tags, are
propagated to resources that AWS CloudFormation supports. See `AWS CloudFormation Resource Tags Type`_ for more details.
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
  The logical name for this stack, which can be used in conjuction with the
  ``output`` lookup. The value here must be unique within the config. If no
  ``stack_name`` is provided, the value here will be used for the name of the
  CloudFormation stack.
**class_path:**
  The python class path to the Blueprint to be used. Specify this or
  ``template_path`` for the stack.
**template_path:**
  Path to raw CloudFormation template (JSON or YAML). Specify this or
  ``class_path`` for the stack.
**description:**
  A short description to apply to the stack. This overwrites any description
  provided in the Blueprint. See: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/template-description-structure.html
**variables:**
  A dictionary of Variables_ to pass into the Blueprint when rendering the
  CloudFormation template. Variables_ can be any valid YAML data
  structure.
**locked:**
  (optional) If set to true, the stack is locked and will not be
  updated unless the stack is passed to stacker via the *--force* flag.
  This is useful for *risky* stacks that you don't want to take the
  risk of allowing CloudFormation to update, but still want to make
  sure get launched when the environment is first created. When ``locked``,
  it's not necessary to specify a ``class_path`` or ``template_path``.
**enabled:**
  (optional) If set to false, the stack is disabled, and will not be
  built or updated. This can allow you to disable stacks in different
  environments.
**protected:**
  (optional) When running an update in non-interactive mode, if a stack has
  *protected* set to *true* and would get changed, stacker will switch to
  interactive mode for that stack, allowing you to approve/skip the change.
**requires:**
  (optional) a list of other stacks this stack requires. This is for explicit
  dependencies - you do not need to set this if you refer to another stack in
  a Parameter, so this is rarely necessary.
**tags:**
  (optional) a dictionary of CloudFormation tags to apply to this stack. This
  will be combined with the global tags, but these tags will take precendence.
**stack_name:**
  (optional) If provided, this will be used as the name of the CloudFormation
  stack. Unlike ``name``, the value doesn't need to be unique within the config,
  since you could have multiple stacks with the same name, but in different
  regions or accounts. (note: the namespace from the environment will be
  prepended to this)
**region**:
  (optional): If provided, specifies the name of the region that the
  CloudFormation stack should reside in. If not provided, the default region
  will be used (``AWS_DEFAULT_REGION``, ``~/.aws/config`` or the ``--region``
  flag). If both ``region`` and ``profile`` are specified, the value here takes
  precedence over the value in the profile.
**profile**:
  (optional): If provided, specifies the name of a AWS profile to use when
  performing AWS API calls for this stack. This can be used to provision stacks
  in multiple accounts or regions.
**stack_policy_path**:
  (optional): If provided, specifies the path to a JSON formatted stack policy
  that will be applied when the CloudFormation stack is created and updated.
  You can use stack policies to prevent CloudFormation from making updates to
  protected resources (e.g. databases). See: https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/protect-stack-resources.html

Stacks Example
~~~~~~~~~~~~~~

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

  common_variables: &common_variables
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

Multi Account/Region Provisioning
---------------------------------

You can use stacker to manage CloudFormation stacks in multiple accounts and
regions, and reference outputs across them.

As an example, let's say you had 3 accounts you wanted to manage:

#) OpsAccount: An AWS account that has IAM users for employees.
#) ProdAccount: An AWS account for a "production" environment.
#) StageAccount: An AWS account for a "staging" environment.

You want employees with IAM user accounts in OpsAccount to be able to assume
roles in both the ProdAccount and StageAccount. You can use stacker to easily
manage this::


  stacks:
    # Create some stacks in both the "prod" and "stage" accounts with IAM roles
    # that employees can use.
    - name: prod/roles
      profile: prod
      class_path: blueprints.Roles
    - name: stage/roles
      profile: stage
      class_path: blueprints.Roles

    # Create a stack in the "ops" account and grant each employee access to
    # assume the roles we created above.
    - name: users
      profile: ops
      class_path: blueprints.IAMUsers
      variables:
        Users:
          john-smith:
            Roles:
              - ${output prod/roles::EmployeeRoleARN}
              - ${output stage/roles::EmployeeRoleARN}


Note how I was able to reference outputs from stacks in multiple accounts using the `output` plugin!

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
.. _stacker_blueprints: https://github.com/cloudtools/stacker_blueprints
.. _`AWS profiles`: https://docs.aws.amazon.com/cli/latest/userguide/cli-multiple-profiles.html
