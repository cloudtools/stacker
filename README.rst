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
both in development, staging, and production without any major issues.

Requirements
============

* Python 2.7
* Python 3.5+

Stacker Command
===============

The ``stacker`` command has sub-commands, similar to git.

Here are some examples:

  ``build``:
    handles taking your stack config and then launching or updating stacks as necessary.

  ``destroy``:
    tears down your stacks
    
  ``diff``:
    compares your currently deployed stack templates to your config files

  ``info``:
    prints information about your currently deployed stacks

We document these sub-commands in full along with others, in the documentation.


Getting Started
===============

``stacker_cookiecutter``: https://github.com/cloudtools/stacker_cookiecutter

  We recommend creating your base `stacker` project using ``stacker_cookiecutter``.
  This tool will install all the needed dependencies and created the project 
  directory structure and files. The resulting files are well documented
  with comments to explain their purpose and examples on how to extend.
  
``stacker_blueprints``: https://github.com/cloudtools/stacker_blueprints

  This repository holds working examples of ``stacker`` blueprints.
  Each blueprint works in isolation and may be referenced, extended, or 
  copied into your project files. The blueprints are written in Python
  and use the troposphere_ library.
  
``stacker reference documentation``:
  
  We document all functionality and features of stacker in our extensive
  reference documentation located at readthedocs_.

``AWS OSS Blog``: https://aws.amazon.com/blogs/opensource/using-aws-codepipeline-and-open-source-tools-for-at-scale-infrastructure-deployment/

  The AWS OSS Blog has a getting started guide using stacker with AWS CodePipeline.
  

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
