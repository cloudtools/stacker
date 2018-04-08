import logging
import os
from subprocess import PIPE, Popen

from stacker.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def _devnull():
    return open(os.devnull, 'wb')


def run_command(provider, context, command, capture=False, interactive=False,
                ignore_status=False, quiet=False, stdin=None, env=None,
                **kwargs):
    """Run a custom command as a hook

    Keyword Arguments:
        command (list or str):
            Command to run
        capture (bool, optional):
            If enabled, capture the command's stdout and stderr, and return
            them in the hook result. Default: false
        interactive (bool, optional):
            If enabled, allow the command to interact with stdin. Otherwise,
            stdin will be set to the null device. Default: false
        ignore_status (bool, optional):
            Don't fail the hook if the command returns a non-zero status.
            Default: false
        quiet (bool, optional):
            Redirect the command's stdout and stderr to the null device,
            silencing all output. Should not be enaled if `capture` is also
            enabled. Default: false
        stdin (str, optional):
            String to send to the stdin of the command. Implicitly disables
            `interactive`.
        env (dict, optional):
            Dictionary of environment variable overrides for the command
            context. Will be merged with the current environment.
        **kwargs:
            Any other arguments will be forwarded to the `subprocess.Popen`
            function. Interesting ones include: `cwd` and `shell`.

    Examples:
        .. code-block:: yaml

            pre_build:
              - path: stacker.hooks.command.run_command
                required: true
                data_key: copy_env
                args:
                  command: ['cp', 'environment.template', 'environment']
              - path: stacker.hooks.command.run_command
                required: true
                data_key: get_git_commit
                args:
                  command: ['git', 'rev-parse', 'HEAD']
                  cwd: ./my-git-repo
                  capture: true
              - path: stacker.hooks.command.run_command
                args:
                  command: `cd $PROJECT_DIR/project; npm install'
                  env:
                    PROJECT_DIR: ./my-project
                  shell: true
    """

    if quiet and capture:
        raise ImproperlyConfigured(
            __name__ + '.run_command',
            'Cannot enable `quiet` and `capture` options simultaneously')

    if quiet:
        out_err_type = _devnull()
    elif capture:
        out_err_type = PIPE
    else:
        out_err_type = None

    if interactive:
        in_type = None
    elif stdin:
        in_type = PIPE
    else:
        in_type = _devnull()

    if env:
        full_env = os.environ.copy()
        full_env.update(env)
        env = full_env

    logger.info('Running command: %s', command)

    proc = Popen(command, stdin=in_type, stdout=out_err_type,
                 stderr=out_err_type, env=env, **kwargs)
    try:
        out, err = proc.communicate(stdin)
        status = proc.wait()

        if status == 0 or ignore_status:
            return {
              'returncode': proc.returncode,
              'stdout': out,
              'stderr': err
            }

        # Don't print the command line again if we already did earlier
        if logger.isEnabledFor(logging.INFO):
            logger.warn('Command failed with returncode %d', status)
        else:
            logger.warn('Command failed with returncode %d: %s', status,
                        command)

        return None
    finally:
        if proc.returncode is None:
            proc.kill()
