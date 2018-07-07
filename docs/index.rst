.. stacker documentation master file, created by
   sphinx-quickstart on Fri Aug 14 09:59:29 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to stacker's documentation!
===================================

stacker is a tool and library used to create & update multiple CloudFormation
stacks. It was originally written at Remind_ and
released to the open source community.

stacker Blueprints are written in troposphere_, though the purpose of
most templates is to keep them as generic as possible and then use
configuration to modify them.

At Remind we use stacker to manage all of our Cloudformation stacks -
both in development, staging and production without any major issues.


Main Features
-------------

- Easily `Create/Update <commands.html#build>`_/`Destroy <commands.html#destroy>`_
  many stacks in parallel (though with an understanding of cross-stack
  dependencies)
- Makes it easy to manage large environments in a single config, while still
  allowing you to break each part of the environment up into its own
  completely separate stack.
- Manages dependencies between stacks, only launching one after all the stacks
  it depends on are finished.
- Only updates stacks that have changed and that have not been explicitly
  locked or disabled.
- Easily pass Outputs from one stack in as Variables on another (which also
  automatically provides an implicit dependency)
- Use `Environments <environments.html>`_ to manage slightly different
  configuration in different environments.
- Use `Lookups <lookups.html>`_ to allow dynamic fetching or altering of
  data used in Variables.
- A diff command for diffing your config against what is running in a live
  CloudFormation environment.
- A small library of pre-shared Blueprints can be found at the
  stacker_blueprints_ repo, making things like setting up a VPC easy.


Contents:

.. toctree::
   :maxdepth: 2

   organizations_using_stacker
   terminology
   config
   environments
   translators
   lookups
   commands
   blueprints
   API Docs <api/modules>



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _Remind: http://www.remind.com/
.. _troposphere: https://github.com/cloudtools/troposphere
.. _stacker_blueprints: https://github.com/cloudtools/stacker_blueprints
