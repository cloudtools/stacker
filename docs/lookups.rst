=======
Lookups
=======

Stacker provides the ability to dynamically replace values in the config via a
concept called lookups. A lookup is meant to take a value and convert
it by calling out to another service or system.

A lookup is denoted in the config with the ``${<lookup type> <lookup
input>}`` syntax. If ``<lookup type>`` isn't provided, the default of
``output`` will be used.

Lookups are only resolved within `Variables
<terminology.html#variables>`_. They can be nested in any part of a YAML
data structure and within another lookup itself.

For example, given the following::

  stacks:
    - name: sg
      class_path: some.stack.blueprint.Blueprint
      variables:
        Roles:
          - ${otherStack::IAMRole}
        Values:
          Env:
            Custom: ${custom ${otherStack::Output}}
            DBUrl: postgres://${dbStack::User}@${dbStack::HostName}

The Blueprint would have access to the following resolved variables
dictionary::

  # variables
  {
    "Roles": ["other-stack-iam-role"],
    "Values": {
      "Env": {
        "Custom": "custom-output",
        "DBUrl": "postgres://user@hostname",
      },
    },
  }

stacker includes the following lookup types:

  - output_
  - kms_
  - xref_

.. _output:

Output Lookup
-------------

The ``output`` lookup type is the default lookup type. It takes a value of
the format: ``<stack name>::<output name>`` and retrieves the output from
the given stack name within the current namespace.

stacker treats output lookups differently than other lookups by auto
adding the referenced stack in the lookup as a requirement to the stack
whose variable the output value is being passed to.

You can specify an output lookup with the following equivalent syntax::

  ConfVariable: ${someStack::SomeOutput}
  ConfVariable: ${output someStack::SomeOutput}

.. _kms:

KMS Lookup
----------

The ``kms`` lookup type decrypts its input value.

As an example, if you have a database and it has a parameter called
``DBPassword`` that you don't want to store in clear text in your config
(maybe because you want to check it into your version control system to
share with the team), you could instead encrypt the value using ``kms``.

For example::

  # We use the aws cli to get the encrypted value for the string
  # "PASSWORD" using the master key called 'myStackerKey' in us-east-1
  $ aws --region us-east-1 kms encrypt --key-id alias/myStackerKey \
      --plaintext "PASSWORD" --output text --query CiphertextBlob

  CiD6bC8t2Y<...encrypted blob...>

  # In stacker we would reference the encrypted value like:
  DBPassword: ${kms us-east-1@CiD6bC8t2Y<...encrypted blob...>}

  # The above would resolve to
  DBPassword: PASSWORD

This requires that the person using stacker has access to the master key used
to encrypt the value.

It is also possible to store the encrypted blob in a file (useful if the
value is large) using the ``file://`` prefix, ie::

  DockerConfig: ${kms file://dockercfg}

.. note::
  Lookups resolve the path specified with `file://` relative to
  the location of the config file, not where the stacker command is run.

.. _xref:

XRef Lookup
-----------

The ``xref`` lookup type is very similar to the ``output`` lookup type, the
difference being that ``xref`` resolves output values from stacks that
aren't contained within the current namespace.

The ``output`` type will take a stack name and use the current context to
expand the fully qualified stack name based on the namespace. ``xref``
skips this expansion because it assumes you've provided it with
the fully qualified stack name already. This allows you to reference
output values from any CloudFormation stack.

Also, unlike the ``output`` lookup type, ``xref`` doesn't impact stack
requirements.

For example::

  ConfVariable: ${xref fully-qualified-stack::SomeOutput}
