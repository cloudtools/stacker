===========
Terminology
===========

blueprint
=========

A python class that is responsible for creating a Cloudformation template.
Usually this is built using troposphere_.

config
======

A yaml config file that defines the `stack definitions`_ for all of the
stacks you want stacker to manage.

environment
===========

A set of variables that can be used inside the config, allowing you to
slightly adjust configs based on which environment you are launching.

local parameter
===============

A set of variables that can be passed down to blueprints, like parameters_,
but which will not be included as parameters in the cloudformation templates.
These are useful for adding a dynamic component to your blueprints.

namespace
=========

A way to uniquely identify a stack. Used to determine the naming of many
things, such as the s3 bucket where compiled templates are stored, as well
as the prefix for stack names.

output
======

A Cloudformation Template concept. Stacks can output values, allowing easy
access to those values. Often used to export the uniqe ID's of resources that
templates create. Stacker makes it simple to pull outputs from one stack and
then use them as a parameter_ in another stack.

parameter
=========

.. _parameters:

Dynamic variables that are passed into stacks when they are being built. In
general these are `Cloudformation Parameters`_, which are passed to the
blueprint upon creation. Can be defined on the command line, or in the config_.

stack
=====

The resulting stack of resources that is created by Cloudformation when it
executes on a template. Each stack managed by stacker is referenced by a
`stack definition`_ in the config_.


stack definition
================

.. _stack definitions:

Defines the stack_ you want to build, usually there are multiple of these in
the config_. It also defines the parameters to be used when building the
stack.

.. _troposphere: https://github.com/cloudtools/troposphere
.. _Cloudformation Parameters: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html
