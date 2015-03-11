stacker
=======

# About

stacker is a tool and library used to create & update multiple CloudFormation
stacks. It was originally written at [Remind](https://www.remind.com/) and
released to the open source community.

stacker StackTemplates are written in [troposphere][], though the purpose of
most templates is to keep them as generic as possible and then use
configuration (and CloudFormation Parameters/Outputs) to modify them.

At this point this is very much alpha software - it is still in heavy
development, and interfaces/configuration/etc may/will likely/most definitely
change :)


[troposphere]: https://github.com/cloudtools/troposphere
