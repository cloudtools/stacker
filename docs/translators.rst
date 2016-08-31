===========
Translators
===========

.. note::
  Translators have been deprecated in favor of `Lookups <lookups.html>`_
  and will be removed in a future release.

Stacker provides the ability to dynamically replace values in the config via a
concept called translators. A translator is meant to take a value and convert
it by calling out to another service or system. This is initially meant to
deal with encrypting fields in your config.

Translators are custom YAML constructors. As an example, if you have a
database and it has a parameter called ``DBPassword`` that you don't want to
store in clear text in your config (maybe because you want to check it into
your version control system to share with the team), you could instead
encrypt the value using ``kms``. For example::

  # We use the aws cli to get the encrypted value for the string
  # "PASSWORD" using the master key called 'myStackerKey' in us-east-1
  $ aws --region us-east-1 kms encrypt --key-id alias/myStackerKey \
      --plaintext "PASSWORD" --output text --query CiphertextBlob

  CiD6bC8t2Y<...encrypted blob...>

  # In stacker we would reference the encrypted value like:
  DBPassword: !kms us-east-1@CiD6bC8t2Y<...encrypted blob...>

  # The above would resolve to
  DBPassword: PASSWORD

This requires that the person using stacker has access to the master key used
to encrypt the value.

It is also possible to store the encrypted blob in a file (useful if the
value is large) using the `file://` prefix, ie::

  DockerConfig: !kms file://dockercfg

.. note::
  Translators resolve the path specified with `file://` relative to
  the location of the config file, not where the stacker command is run.
