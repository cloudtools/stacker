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

.. _config file:

A YAML config file that defines the `stack definitions`_ for all of the
stacks you want stacker to manage.


context
=======

Context is responsible for translating the values passed in via the
command line and specified in the config_ to stacks_.

.. _troposphere: https://github.com/cloudtools/troposphere
.. _CloudFormation Parameters: http://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/parameters-section-structure.html


environment
===========

A set of variables that can be used inside the config, allowing you to
slightly adjust configs based on which environment you are launching.


graph
=====

A mapping of **object name** to **set/list of dependencies**.

A graph is constructed for each execution of Stacker from the contents of the
config_ file.

Example
-------

.. code-block:: json

    {
        "stack1": [],
        "stack2": [
            "stack1"
        ]
    }

- **stack1** depends on nothing.
- **stack2** depends on **stack1**


lookup
======

A method for expanding values in the config_ at build time. By default
lookups are used to reference Output values from other stacks_ within the
same namespace_.


namespace
=========

A way to uniquely identify a stack. Used to determine the naming of many
things, such as the S3 bucket where compiled templates are stored, as well
as the prefix for stack names.


output
======

A CloudFormation Template concept. Stacks can output values, allowing easy
access to those values. Often used to export the unique ID's of resources that
templates create. Stacker makes it simple to pull outputs from one stack and
then use them as a variable_ in another stack.


persistent graph
================

A graph_ that is persisted between Stacker executions. It is stored in in the
Stack `S3 bucket <config.html#s3-bucket>`_.


provider
========

Provider that supports provisioning rendered blueprints_. By default, an
AWS provider is used.


stack
=====

.. _stacks:

The resulting stack of resources that is created by CloudFormation when it
executes a template. Each stack managed by stacker is defined by a
`stack definition`_ in the config_.


stack definition
================

.. _stack definitions:

Defines the stack_ you want to build, usually there are multiple of these in
the config_. It also defines the variables_ to be used when building the
stack_.


variable
========

.. _variables:

Dynamic variables that are passed into stacks when they are being built.
Variables are defined within the config_.

