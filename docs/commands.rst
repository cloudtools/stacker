========
Commands
========

Build
-----

Build is used to create/update the stacks_ provided in the `config file`_. It
automatically figures out any dependencies between stacks_, and creates them
in parallel safely (if a stack_ depends on another stack_, it will wait for
that stack_ to be finished before updating/creating).

If using a `persistent graph`_, build actions more like *apply*. It will
create/update stacks_ defined in the `config file`_ as expected but, it will
also delete any stacks_ that exist in the `persistent graph`_ but are no longer
present in the `config file`_.

It also provides the **--dump** flag for testing out blueprints_ before
pushing them up into CloudFormation.
Even then, some errors might only be noticed after first submitting a stack_,
at which point it can no longer be updated by Stacker.
When that situation is detected in interactive mode, you will be prompted to
delete and re-create the stack_, so that you don't need to do it manually in
the AWS console.
If that behavior is also desired in non-interactive mode, enable the
**--recreate-failed** flag.

::

  # stacker build -h
  usage: stacker build [-h] [-e ENV=VALUE] [-r REGION] [-v] [-i]
                       [--replacements-only] [--recreate-failed] [-o]
                       [--force STACKNAME] [--stacks STACKNAME] [-t] [-d DUMP]
                       [environment] config

  Launches or updates CloudFormation stacks based on the given config. Stacker
  is smart enough to figure out if anything (the template or parameters) have
  changed for a given stack. If nothing has changed, stacker will correctly skip
  executing anything against the stack.

  If using a persistent graph, Stacker will also delete any stacks that exist
  in the persistent graph but are no longer present in the config file.

  positional arguments:
    environment           Path to a simple `key: value` pair environment file.
                          The values in the environment file can be used in the
                          stack config as if it were a string.Template type:
                          https://docs.python.org/2/library/string.html
                          #template-strings.
    config                The config file where stack configuration is located.
                          Must be in yaml format. If `-` is provided, then the
                          config will be read from stdin.

  optional arguments:
    -h, --help            show this help message and exit
    -e ENV=VALUE, --env ENV=VALUE
                          Adds environment key/value pairs from the command
                          line. Overrides your environment file settings. Can be
                          specified more than once.
    -r REGION, --region REGION
                          The AWS region to launch in.
    -v, --verbose         Increase output verbosity. May be specified up to
                          twice.
    -i, --interactive     Enable interactive mode. If specified, this will use
                          the AWS interactive provider, which leverages
                          Cloudformation Change Sets to display changes before
                          running cloudformation templates. You'll be asked if
                          you want to execute each change set. If you only want
                          to authorize replacements, run with "--replacements-
                          only" as well.
    --replacements-only   If interactive mode is enabled, stacker will only
                          prompt to authorize replacements.
    --recreate-failed     Destroy and re-create stacks that are stuck in a
                          failed state from an initial deployment when updating.
    -o, --outline         Print an outline of what steps will be taken to build
                          the stacks
    --force STACKNAME     If a stackname is provided to --force, it will be
                          updated, even if it is locked in the config.
    --stacks STACKNAME    Only work on the stacks given. Can be specified more
                          than once. If not specified then stacker will work on
                          all stacks in the config file.
    -t, --tail            Tail the CloudFormation logs while working with stacks
    -d DUMP, --dump DUMP  Dump the rendered Cloudformation templates to a
                          directory

Destroy
-------

Destroy handles the tearing down of CloudFormation stacks defined in the
`config file`_ and `persistent graph`_ (if enabled). It figures out any
dependencies that may exist, and destroys the stacks_ in the correct order
(in parallel if all dependent stacks have already been destroyed).

::

  # stacker destroy -h
  usage: stacker destroy [-h] [-e ENV=VALUE] [-r REGION] [-v] [-i]
                         [--replacements-only] [-f] [--stacks STACKNAME] [-t]
                         environment config

  Destroys CloudFormation stacks based on the given config and persistent graph
  (if enabled). Stacker will determine the order in which stacks should be
  destroyed based on any manual requirements they specify or output values they
  rely on from other stacks.

  positional arguments:
    environment           Path to a simple `key: value` pair environment file.
                          The values in the environment file can be used in the
                          stack config as if it were a string.Template type:
                          https://docs.python.org/2/library/string.html
                          #template-strings. Must define at least a "namespace".
    config                The config file where stack configuration is located.
                          Must be in yaml format. If `-` is provided, then the
                          config will be read from stdin.

  optional arguments:
    -h, --help            show this help message and exit
    -e ENV=VALUE, --env ENV=VALUE
                          Adds environment key/value pairs from the command
                          line. Overrides your environment file settings. Can be
                          specified more than once.
    -r REGION, --region REGION
                          The AWS region to launch in.
    -v, --verbose         Increase output verbosity. May be specified up to
                          twice.
    -i, --interactive     Enable interactive mode. If specified, this will use
                          the AWS interactive provider, which leverages
                          Cloudformation Change Sets to display changes before
                          running cloudformation templates. You'll be asked if
                          you want to execute each change set. If you only want
                          to authorize replacements, run with "--replacements-
                          only" as well.
    --replacements-only   If interactive mode is enabled, stacker will only
                          prompt to authorize replacements.
    -f, --force           Whether or not you want to go through with destroying
                          the stacks
    --stacks STACKNAME    Only work on the stacks given. Can be specified more
                          than once. If not specified then stacker will work on
                          all stacks in the config file.
    -t, --tail            Tail the CloudFormation logs while working with stacks

Diff
----

Diff attempts to show the differences between what stacker expects to push up
into CloudFormation, and what already exists in CloudFormation.  This command
is not perfect, as following things like *Ref* and *GetAtt* are not currently
possible, but it should give a good idea if anything has changed.

::

  # stacker diff -h
  usage: stacker diff [-h] [-e ENV=VALUE] [-r REGION] [-v] [-i]
                      [--replacements-only] [--force STACKNAME]
                      [--stacks STACKNAME]
                      environment config

  Diffs the config against the currently running CloudFormation stacks Sometimes
  small changes can have big impacts. Run "stacker diff" before "stacker build"
  to detect bad things(tm) from happening in advance!

  positional arguments:
    environment           Path to a simple `key: value` pair environment file.
                          The values in the environment file can be used in the
                          stack config as if it were a string.Template type:
                          https://docs.python.org/2/library/string.html
                          #template-strings. Must define at least a "namespace".
    config                The config file where stack configuration is located.
                          Must be in yaml format. If `-` is provided, then the
                          config will be read from stdin.

  optional arguments:
    -h, --help            show this help message and exit
    -e ENV=VALUE, --env ENV=VALUE
                          Adds environment key/value pairs from the command
                          line. Overrides your environment file settings. Can be
                          specified more than once.
    -r REGION, --region REGION
                          The AWS region to launch in.
    -v, --verbose         Increase output verbosity. May be specified up to
                          twice.
    -i, --interactive     Enable interactive mode. If specified, this will use
                          the AWS interactive provider, which leverages
                          Cloudformation Change Sets to display changes before
                          running cloudformation templates. You'll be asked if
                          you want to execute each change set. If you only want
                          to authorize replacements, run with "--replacements-
                          only" as well.
    --replacements-only   If interactive mode is enabled, stacker will only
                          prompt to authorize replacements.
    --force STACKNAME     If a stackname is provided to --force, it will be
                          diffed, even if it is locked in the config.
    --stacks STACKNAME    Only work on the stacks given. Can be specified more
                          than once. If not specified then stacker will work on
                          all stacks in the config file.

Graph
-----

Prints the the relationships between steps as a `graph <terminology.html#graph>`_.

::

  positional arguments:
    environment           Path to a simple `key: value` pair environment file.
                          The values in the environment file can be used in the
                          stack config as if it were a string.Template type:
                          https://docs.python.org/2/library/string.html
                          #template-strings.
    config                The config file where stack configuration is located.
                          Must be in yaml format. If `-` is provided, then the
                          config will be read from stdin.

  optional arguments:
    -h, --help            show this help message and exit
    -e ENV=VALUE, --env ENV=VALUE
                          Adds environment key/value pairs from the command
                          line. Overrides your environment file settings. Can be
                          specified more than once.
    -r REGION, --region REGION
                          The default AWS region to use for all AWS API calls.
    -p PROFILE, --profile PROFILE
                          The default AWS profile to use for all AWS API calls.
                          If not specified, the default will be according to htt
                          p://boto3.readthedocs.io/en/latest/guide/configuration
                          .html.
    -v, --verbose         Increase output verbosity. May be specified up to
                          twice.
    -i, --interactive     Enable interactive mode. If specified, this will use
                          the AWS interactive provider, which leverages
                          Cloudformation Change Sets to display changes before
                          running cloudformation templates. You'll be asked if
                          you want to execute each change set. If you only want
                          to authorize replacements, run with "--replacements-
                          only" as well.
    --replacements-only   If interactive mode is enabled, stacker will only
                          prompt to authorize replacements.
    --recreate-failed     Destroy and re-create stacks that are stuck in a
                          failed state from an initial deployment when updating.
    -f {json,dot}, --format {json,dot}
                          The format to print the graph in.
    --reduce              When provided, this will create a graph with less
                          edges, by performing a transitive reduction on the
                          underlying graph. While this will produce a less noisy
                          graph, it is slower.

Info
----

Info displays information on the CloudFormation stacks based on the given
config.

::

  # stacker info -h
  usage: stacker info [-h] [-e ENV=VALUE] [-r REGION] [-v] [-i]
                      [--replacements-only] [--stacks STACKNAME]
                      environment config

  Gets information on the CloudFormation stacks based on the given config.

  positional arguments:
    environment           Path to a simple `key: value` pair environment file.
                          The values in the environment file can be used in the
                          stack config as if it were a string.Template type:
                          https://docs.python.org/2/library/string.html
                          #template-strings. Must define at least a "namespace".
    config                The config file where stack configuration is located.
                          Must be in yaml format. If `-` is provided, then the
                          config will be read from stdin.

  optional arguments:
    -h, --help            show this help message and exit
    -e ENV=VALUE, --env ENV=VALUE
                          Adds environment key/value pairs from the command
                          line. Overrides your environment file settings. Can be
                          specified more than once.
    -r REGION, --region REGION
                          The AWS region to launch in.
    -v, --verbose         Increase output verbosity. May be specified up to
                          twice.
    -i, --interactive     Enable interactive mode. If specified, this will use
                          the AWS interactive provider, which leverages
                          Cloudformation Change Sets to display changes before
                          running cloudformation templates. You'll be asked if
                          you want to execute each change set. If you only want
                          to authorize replacements, run with "--replacements-
                          only" as well.
    --replacements-only   If interactive mode is enabled, stacker will only
                          prompt to authorize replacements.
    --stacks STACKNAME    Only work on the stacks given. Can be specified more
                          than once. If not specified then stacker will work on
                          all stacks in the config file.

.. _blueprints: terminology.html#blueprint
.. _config file: terminology.html#config
.. _persistent graph: config.html#persistent-graph
.. _stack: terminology.html#stack
.. _stacks: terminology.html#stack
