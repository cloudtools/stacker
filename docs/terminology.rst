===========
Terminology
===========

blueprint
=========

.. _blueprints:

A python class that is responsible for creating a CloudFormation template.
Usually this is built using troposphere_.

config
======

A YAML config file that defines the `stack definitions`_ for all of the
stacks you want stacker to manage.

environment
===========

A set of variables that can be used inside the config, allowing you to
slightly adjust configs based on which environment you are launching.

namespace
=========

A way to uniquely identify a stack. Used to determine the naming of many
things, such as the S3 bucket where compiled templates are stored, as well
as the prefix for stack names.

stack definition
================

.. _stack definitions:

Defines the stack_ you want to build, usually there are multiple of these in
the config_. It also defines the variables_ to be used when building the
stack_.

stack
=====

.. _stacks:

The resulting stack of resources that is created by CloudFormation when it
executes a template. Each stack managed by stacker is defined by a
`stack definition`_ in the config_.

output
======

A CloudFormation Template concept. Stacks can output values, allowing easy
access to those values. Often used to export the unique ID's of resources that
templates create. Stacker makes it simple to pull outputs from one stack and
then use them as a variable_ in another stack.

variable
========

.. _variables:

Dynamic variables that are passed into stacks when they are being built.
Variables are defined within the config_.

lookup
======

A method for expanding values in the config_ at build time. By default
lookups are used to reference Output values from other stacks_ within the
same namespace_.

provider
========

Provider that supports provisioning rendered blueprints_. By default, an
AWS provider is used.

context
=======

Context is responsible for translating the values passed in via the
command line and specified in the config_ to stacks_.

.. _troposphere: https://github.com/cloudtools/troposphere
.. _CloudFormation Parameters: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html
