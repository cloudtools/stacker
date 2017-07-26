============
Environments
============

When running stacker, you can optionally provide an "environment" file. The
stacker config file will be interpolated as a `string.Template
<https://docs.python.org/2/library/string.html#template-strings>`_ using the
key/value pairs from the environment file. The format of the file is a single
key/value per line, separated by a colon (**:**), like this::

  vpcID: vpc-12345678

Provided the key/value vpcID above, you will now be able to use this in
your configs for the specific environment you are deploying into. They
act as keys that can be used in your config file, providing a sort of
templating ability. This allows you to change the values of your config
based on the environment you are in. For example, if you have a *webserver*
stack, and you need to provide it a Parameter for the instance size it
should use, you would have something like this in your config file::

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
  web_instance_type: m3.medium

  # in the file: prod.env
  web_instance_type: c4.xlarge

  # in your config file:
  stacks:
    - name: webservers
      class_path: stacker_blueprints.asg.AutoscalingGroup
      parameters:
        InstanceType: ${web_instance_type}

.. note::
  Namespace defined in the environment file has been deprecated in favor of
  defining the namespace in the config and will be removed in a future release.
