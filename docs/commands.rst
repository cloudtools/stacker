========
Commands
========

Build
-----

::

  # stacker build -h
  usage: stacker build [-h] [-p PARAMETER=VALUE] [-e ENV=VALUE] [-r REGION] [-v] [-m MAX_ZONES] [-o] [--force STACKNAME] [--stacks STACKNAME] [-t] [-d DUMP]
                       environment config

  Launches or updates CloudFormation stacks based on the given config. Stacker is smart enough to figure out if anything (the template or parameters) have changed for
  a given stack. If nothing has changed, stacker will correctly skip executing anything against the stack.

  positional arguments:
    environment           Path to a simple `key: value` pair environment file. The values in the environment file can be used in the stack config as if it were a
                          string.Template type: https://docs.python.org/2/library/string.html#template-strings. Must define at least a 'namespace'.
    config                The config file where stack configuration is located. Must be in yaml format.

  optional arguments:
    -h, --help            show this help message and exit
    -p PARAMETER=VALUE, --parameter PARAMETER=VALUE
                          Adds parameters from the command line that can be used inside any of the stacks being built. Can be specified more than once.
    -e ENV=VALUE, --env ENV=VALUE
                          Adds environment key/value pairs from the command line. Overrides your environment file settings. Can be specified more than once.
    -r REGION, --region REGION
                          The AWS region to launch in. Default: us-east-1
    -v, --verbose         Increase output verbosity. May be specified up to twice.
    -m MAX_ZONES, --max-zones MAX_ZONES
                          Gives you the ability to limit the # of zones that resources will be launched in. If not given, then resources will be launched in all
                          available availability zones.
    -o, --outline         Print an outline of what steps will be taken to build the stacks
    --force STACKNAME     If a stackname is provided to --force, it will be updated, even if it is locked in the config.
    --stacks STACKNAME    Only work on the stacks given. Can be specified more than once. If not specified then stacker will work on all stacks in the config file.
    -t, --tail            Tail the CloudFormation logs while workingwith stacks
    -d DUMP, --dump DUMP  Dump the rendered Cloudformation templates to a directory


Destroy
-------

::

  # stacker destroy -h
  usage: stacker destroy [-h] [-p PARAMETER=VALUE] [-e ENV=VALUE] [-r REGION] [-v] [-f] [-t] environment config

  Destroys CloudFormation stacks based on the given config. Stacker will determine the order in which stacks should be destroyed based on any manual requirements they
  specify or output values they rely on from other stacks.

  positional arguments:
    environment           Path to a simple `key: value` pair environment file. The values in the environment file can be used in the stack config as if it were a
                          string.Template type: https://docs.python.org/2/library/string.html#template-strings. Must define at least a 'namespace'.
    config                The config file where stack configuration is located. Must be in yaml format.

  optional arguments:
    -h, --help            show this help message and exit
    -p PARAMETER=VALUE, --parameter PARAMETER=VALUE
                          Adds parameters from the command line that can be used inside any of the stacks being built. Can be specified more than once.
    -e ENV=VALUE, --env ENV=VALUE
                          Adds environment key/value pairs from the command line. Overrides your environment file settings. Can be specified more than once.
    -r REGION, --region REGION
                          The AWS region to launch in. Default: us-east-1
    -v, --verbose         Increase output verbosity. May be specified up to twice.
    -f, --force           Whether or not you want to go through with destroying the stacks
    -t, --tail            Tail the CloudFormation logs while workingwith stacks


Info
----

::

  # stacker info -h
  usage: stacker info [-h] [-p PARAMETER=VALUE] [-e ENV=VALUE] [-r REGION] [-v] [--stacks STACKNAME] environment config

  Gets information on the CloudFormation stacks based on the given config.

  positional arguments:
    environment           Path to a simple `key: value` pair environment file. The values in the environment file can be used in the stack config as if it were a
                          string.Template type: https://docs.python.org/2/library/string.html#template-strings. Must define at least a 'namespace'.
    config                The config file where stack configuration is located. Must be in yaml format.

  optional arguments:
    -h, --help            show this help message and exit
    -p PARAMETER=VALUE, --parameter PARAMETER=VALUE
                          Adds parameters from the command line that can be used inside any of the stacks being built. Can be specified more than once.
    -e ENV=VALUE, --env ENV=VALUE
                          Adds environment key/value pairs from the command line. Overrides your environment file settings. Can be specified more than once.
    -r REGION, --region REGION
                          The AWS region to launch in. Default: us-east-1
    -v, --verbose         Increase output verbosity. May be specified up to twice.
    --stacks STACKNAME    Only work on the stacks given. Can be specified more than once. If not specified then stacker will work on all stacks in the config file.

Diff
----

::

  # stacker diff -h
  usage: stacker diff [-h] [-p PARAMETER=VALUE] [-e ENV=VALUE] [-r REGION] [-v] [--force STACKNAME] [--stacks STACKNAME] environment config

  Diffs the config against the currently running CloudFormation stacks Sometimes small changes can have big impacts. Run 'stacker diff' before 'stacker build' to
  detect bad things(tm) from happening in advance!

  positional arguments:
    environment           Path to a simple `key: value` pair environment file. The values in the environment file can be used in the stack config as if it were a
                          string.Template type: https://docs.python.org/2/library/string.html#template-strings. Must define at least a 'namespace'.
    config                The config file where stack configuration is located. Must be in yaml format.

  optional arguments:
    -h, --help            show this help message and exit
    -p PARAMETER=VALUE, --parameter PARAMETER=VALUE
                          Adds parameters from the command line that can be used inside any of the stacks being built. Can be specified more than once.
    -e ENV=VALUE, --env ENV=VALUE
                          Adds environment key/value pairs from the command line. Overrides your environment file settings. Can be specified more than once.
    -r REGION, --region REGION
                          The AWS region to launch in. Default: us-east-1
    -v, --verbose         Increase output verbosity. May be specified up to twice.
    --force STACKNAME     If a stackname is provided to --force, it will be diffed, even if it is locked in the config.
    --stacks STACKNAME    Only work on the stacks given. Can be specified more than once. If not specified then stacker will work on all stacks in the config file.
