import importlib
import logging
import re
import sys
import time

from boto.route53.record import ResourceRecordSets

logger = logging.getLogger(__name__)


def retry_with_backoff(function, args=None, kwargs=None, attempts=5,
                       min_delay=1, max_delay=3, exc_list=None,
                       retry_checker=None):
    """Retries function, catching expected Exceptions.

    Each retry has a delay between `min_delay` and `max_delay` seconds,
    increasing with each attempt.

    Args:
        function (function): The function to call.
        args (Optional(list)): A list of positional arguments to pass to the
            given function.
        kwargs (Optional(dict)): Keyword arguments to pass to the given
            function.
        attempts (Optional(int)): The # of times to retry the function.
            Default: 5
        min_delay (Optional(int)): The minimum time to delay retries, in
            seconds. Default: 1
        max_delay (Optional(int)): The maximum time to delay retries, in
            seconds. Default: 5
        exc_list (Optional(list)): A list of :class:`Exception` classes that
            should be retried. Default: [:class:`Exception`,]
        retry_checker (Optional(func)): An optional function that is used to
            do a deeper analysis on the received :class:`Exception` to
            determine if it qualifies for retry. Receives a single argument,
            the :class:`Exception` object that was caught. Should return
            True if it should be retried.

    Returns:
        variable: Returns whatever the given function returns.

    Raises:
        :class:`Exception`: Raises whatever exception the given function
            raises, if unable to succeed within the given number of attempts.
    """
    args = args or []
    kwargs = kwargs or {}
    attempt = 0
    if not exc_list:
        exc_list = (Exception, )
    while True:
        attempt += 1
        logger.debug("Calling %s, attempt %d.", function, attempt)
        sleep_time = min(max_delay, min_delay * attempt)
        try:
            return function(*args, **kwargs)
        except exc_list as e:
            # If there is no retry checker function, or if there is and it
            # returns True, then go ahead and retry
            if not retry_checker or retry_checker(e):
                if attempt == attempts:
                    logger.error("Function %s failed after %s retries. Giving "
                                 "up.", function.func_name, attempts)
                    raise
                logger.debug("Caught expected exception: %r", e)
            # If there is a retry checker function, and it returned False,
            # do not retry
            else:
                raise
        time.sleep(sleep_time)


def camel_to_snake(name):
    """Converts CamelCase to snake_case.

    Args:
        name (string): The name to convert from CamelCase to snake_case.

    Returns:
        string: Converted string.
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def convert_class_name(kls):
    """Gets a string that represents a given class.

    Args:
        kls (class): The class being analyzed for its name.

    Returns:
        string: The name of the given kls.
    """
    return camel_to_snake(kls.__name__)


def create_route53_zone(conn, zone_name):
    """Create's the given zone_name if it doesn't already exists.

    Also sets the SOA negative caching TTL to something short (300 seconds).

    Args:
        conn (:class:`boto.route53.Route53Connection`): The connection used
            to interact with Route53's API.
        zone_name (string): The name of the DNS hosted zone to create.
    """
    if not zone_name.endswith('.'):
        zone_name += '.'
    zone = conn.get_zone(zone_name)
    if not zone:
        logger.debug("Zone %s does not exist, creating.", zone_name)
        zone = conn.create_zone(zone_name)
    # Update SOA to lower negative caching value
    soa = zone.find_records(zone_name, 'SOA')
    old_soa_body = soa.resource_records[0]
    old_soa_parts = old_soa_body.split(' ')
    # If the negative cache value is already 300, don't update it.
    if old_soa_parts[-1] == '300':
        return
    logger.debug("Updating negative caching value on zone %s to 300.",
                 zone_name)
    new_soa_body = ' '.join(old_soa_body.split(' ')[:-1]) + ' 300'
    changes = ResourceRecordSets(conn, zone.id)
    delete_soa = changes.add_change('DELETE', zone.name, 'SOA', soa.ttl)
    delete_soa.add_value(old_soa_body)
    create_soa = changes.add_change('CREATE', zone.name, 'SOA', soa.ttl)
    create_soa.add_value(new_soa_body)
    changes.commit()


def load_object_from_string(fqcn):
    """Converts '.' delimited strings to a python object.

    Given a '.' delimited string representing the full path to an object
    (function, class, variable) inside a module, return that object.  Example:

    load_object_from_string('os.path.basename')
    load_object_from_string('logging.Logger')
    load_object_from_string('LocalClassName')
    """
    module_path = '__main__'
    object_name = fqcn
    if '.' in fqcn:
        module_path, object_name = fqcn.rsplit('.', 1)
        importlib.import_module(module_path)
    return getattr(sys.modules[module_path], object_name)


def uppercase_first_letter(s):
    """Return string 's' with first character upper case."""
    return s[0].upper() + s[1:]


def cf_safe_name(name):
    """Converts a name to a safe string for a Cloudformation resource.

    Given a string, returns a name that is safe for use as a CloudFormation
    Resource. (ie: Only alphanumeric characters)
    """
    alphanumeric = r'[a-zA-Z0-9]+'
    parts = re.findall(alphanumeric, name)
    return ''.join([uppercase_first_letter(part) for part in parts])


# TODO: perhaps make this a part of the builder?
def handle_hooks(stage, hooks, region, context):
    """ Used to handle pre/post_build hooks.

    These are pieces of code that we want to run before/after the builder
    builds the stacks.

    Args:
        stage (string): The current stage (pre_run, post_run, etc).
        hooks (list): A list of dictionaries containing the hooks to execute.
        region (string): The AWS region the current stacker run is executing
            in.
        context (:class:`stacker.context.Context`): The current stacker
            context.
    """
    if not hooks:
        logger.debug("No %s hooks defined.", stage)
        return

    hook_paths = []
    for i, h in enumerate(hooks):
        try:
            hook_paths.append(h['path'])
        except KeyError:
            raise ValueError("%s hook #%d missing path." % (stage, i))

    logger.info("Executing %s hooks: %s", stage, ", ".join(hook_paths))
    for hook in hooks:
        required = hook.get('required', True)
        kwargs = hook.get('args', {})
        try:
            method = load_object_from_string(hook['path'])
        except (AttributeError, ImportError):
            logger.exception("Unable to load method at %s:", hook['path'])
            if required:
                raise
            continue
        try:
            result = method(
                region,
                context.namespace,
                context.mappings,
                context.parameters,
                **kwargs
            )
        except Exception:
            logger.exception("Method %s threw an exception:", hook['path'])
            if required:
                raise
            continue
        if not result:
            if required:
                logger.error("Required hook %s failed. Return value: %s",
                             hook['path'], result)
                sys.exit(1)
            logger.warning("Non-required hook %s failed. Return value: %s",
                           hook['path'], result)
