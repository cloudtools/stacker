=======
stacker
=======

.. image:: https://readthedocs.org/projects/stacker/badge/?version=latest
   :target: http://stacker.readthedocs.org/en/latest/

.. image:: https://circleci.com/gh/cloudtools/stacker.svg?style=shield
   :target: https://circleci.com/gh/cloudtools/stacker

.. image:: https://empire-slack.herokuapp.com/badge.svg
   :target: https://empire-slack.herokuapp.com

.. image:: https://badge.fury.io/py/stacker.svg
   :target: https://badge.fury.io/py/stacker

.. image:: https://landscape.io/github/cloudtools/stacker/master/landscape.svg?style=flat
   :target: https://landscape.io/github/cloudtools/stacker/master
   :alt: Code Health

.. image:: https://codecov.io/gh/cloudtools/stacker/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/cloudtools/stacker
   :alt: codecov


For full documentation, please see the readthedocs_ site.

`Click here to join the Slack team`_ for stacker, and then join the #stacker
channel!

About
=====

stacker is a tool and library used to create & update multiple CloudFormation
stacks. It was originally written at Remind_ and
released to the open source community.

stacker Blueprints are written in troposphere_, though the purpose of
most templates is to keep them as generic as possible and then use
configuration to modify them.

At Remind we use stacker to manage all of our Cloudformation stacks -
both in development, staging and production without any major issues.

Requirements
============

* Python 2.7
* Python 3.5+

Stacker Command
===============

The stacker command is built to have sub-commands, much like git. Currently the
commands are:

- ``build`` which handles taking your stack config and then launching or
  updating stacks as necessary.
- ``destroy`` which tears down your stacks
- ``diff`` which compares your currently deployed stack templates to your
  config files
- ``info`` which prints information about your currently deployed stacks

Docker
======

Stack can also be executed from Docker. Use this method to run stacker if you
want to avoid setting up a python environment::

  docker run -it -v `pwd`:/stacks remind101/stacker build ...

.. _Remind: http://www.remind.com/
.. _troposphere: https://github.com/cloudtools/troposphere
.. _string.Template: https://docs.python.org/2/library/string.html#template-strings
.. _readthedocs: http://stacker.readthedocs.io/en/latest/
.. _`Click here to join the Slack team`: https://empire-slack.herokuapp.com
