============
Environments
============

When running stacker, you can optionally provide an "environment" file. The
environment file defines values, which can then be referred to by name from
your stack config file. The environment file is interpreted as YAML if it
ends in `.yaml` or `.yml`, otherwise it's interpreted as simple key/value
pairs.

Key/Value environments
----------------------

The stacker config file will be interpolated as a `string.Template
<https://docs.python.org/2/library/string.html#template-strings>`_ using the
key/value pairs from the environment file. The format of the file is a single
key/value per line, separated by a colon (**:**), like this::

  vpcID: vpc-12345678

Provided the key/value vpcID above, you will now be able to use this in
your configs for the specific environment you are deploying into. They
act as keys that can be used in your config file, providing a sort of
templating ability. This allows you to change the values of your config
based on the environment you are in. For example, if you have a *webserver*
stack, and you need to provide it a variable for the instance size it
should use, you would have something like this in your config file::

  stacks:
    - name: webservers
      class_path: stacker_blueprints.asg.AutoscalingGroup
      variables:
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
      variables:
        InstanceType: ${web_instance_type}

YAML environments
-----------------

YAML environments allow for more complex environment configuration rather
than simple text substitution, and support YAML features like anchors and
references. To build on the example above, let's define a stack that's
a little more complex::

  stacks:
    - name: webservers
      class_path: stacker_blueprints.asg.AutoscalingGroup
      variables:
        InstanceType: ${web_instance_type}
        IngressCIDRsByPort: ${ingress_cidrs_by_port}

We've defined a stack which expects a list of ingress CIDR's allowed access to
each port. Our environment files would look like this::

  # in the file: stage.env
  web_instance_type: m3.medium
  ingress_cidrs_by_port:
    80:
      - 192.168.1.0/8
    8080:
      - 0.0.0.0/0

  # in the file: prod.env
  web_instance_type: c4.xlarge
  ingress_cidrs_by_port:
    80:
      - 192.168.1.0/8
    443:
      - 10.0.0.0/16
      - 10.1.0.0/16

The YAML format allows for specifying lists, maps, and supports all `pyyaml`
functionality allowed in `safe_load()` function.

Variable substitution in the YAML case is a bit more complex than in the
`string.Template` case. Objects can only be substituted for variables in the
case where we perform a full substitution, such as this::

  vpcID: ${vpc_variable}

We can not substitute an object in a sub-string, such as this::

  vpcID: prefix-${vpc_variable}

It makes no sense to substitute a complex object in this case, and we will raise
an error if that happens. You can still perform this substitution with
primitives; numbers, strings, but not dicts or lists.

.. note::
  Namespace defined in the environment file has been deprecated in favor of
  defining the namespace in the config and will be removed in a future release.
