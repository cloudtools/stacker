.. stacker documentation master file, created by
   sphinx-quickstart on Fri Aug 14 09:59:29 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to stacker's documentation!
===================================

stacker is a tool and library used to create & update multiple CloudFormation
stacks. It was originally written at Remind_ and
released to the open source community.

stacker StackTemplates are written in troposphere_, though the purpose of
most templates is to keep them as generic as possible and then use
configuration (and CloudFormation Parameters/Outputs) to modify them.

At this point this is very much alpha software - it is still in heavy
development, and interfaces/configuration/etc may/will likely/most definitely
change :)

That said, at Remind we use stacker to manage all of our Cloudformation stacks-
both in development, staging and production without any major issues.


Contents:

.. toctree::
   :maxdepth: 2

   API Docs <api/modules>



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. _Remind: http://www.remind.com/
.. _troposphere: https://github.com/cloudtools/troposphere
