============
Environments
============

When running stacker, you can optionally provide an "environment" file. The
stacker config file will be interpolated as a `string.Template
<https://docs.python.org/2/library/string.html#template-strings>`_ using the
key/value pairs from the environment file. The format of the file is a single
key/value per line, separated by a colon (**:**), like this::

  namespace: stage-mycompany

Provided the namespace above, and a stack name of **vpc** you will end up with
a stack in CloudFormation with the name **stage-mycompany-vpc**.

Environments can be used for a lot more than the namespace, however. They act
as keys that can be used in your config file, providing a sort of templating.
This allows you to change the values of your config based on the environment
you are in. For example, if you have a *webserver* stack, and you need to
provide it a Parameter for the instance size it should use, you would have
something like this in your config file::

  stacks:
    - name: webservers
      class_path: stacker_blueprints.asg.AutoscalingGroup
      parameters:
        InstanceType: m3.medium

But what if you needed more CPU in your production environment, but not in your
staging? Without Environments, you'd need a separate config for each. With
environments, you can simply define two different environment files with the
appropriate *InstanceType* in each, and then use the key in the environment
files in your config. For example::

  # in the file: stage.env
  namespace: stage-mycompany
  web_instance_type: m3.medium

  # in the file: prod.env
  namespace: prod-mycompany
  web_instance_type: c4.xlarge

  # in your config file:
  stacks:
    - name: webservers
      class_path: stacker_blueprints.asg.AutoscalingGroup
      parameters:
        InstanceType: ${web_instance_type}
