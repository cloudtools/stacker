import logging

logger = logging.getLogger(__name__)

import time
import re
import importlib
import sys

from boto.route53.record import ResourceRecordSets


def retry_with_backoff(function, args=None, kwargs=None, attempts=5,
                       min_delay=1, max_delay=3, exc_list=None):
    """ Retries function, catching expected Exceptions. """
    args = args or []
    kwargs = kwargs or {}
    attempt = 0
    if not exc_list:
        exc_list = (Exception, )
    while True:
        attempt += 1
        sleep_time = min(max_delay, min_delay * attempt)
        try:
            return function(*args, **kwargs)
        except exc_list as e:
            if attempt == attempts:
                logger.error("Function %s failed after %s retries. Giving up.",
                             function.func_name, attempts)
                raise
            logger.debug("Caught expected exception: %r", e)
        time.sleep(sleep_time)


def camel_to_snake(name):
    """ Converts CamelCase to snake_case. """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def convert_class_name(kls):
    """ Gets a string that represents a given class. """
    return camel_to_snake(kls.__name__)


def create_route53_zone(conn, zone_name):
    """ Create's the given zone_name if it doesn't already exists.

    Also sets the SOA negative caching TTL to something short (300 seconds).
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
    """ Given a '.' delimited string representing the full path to an object
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
    """ Return string 's' with first character upper case. """
    return s[0].upper() + s[1:]


def cf_safe_name(name):
    """ Given a string, returns a name that is safe for use as a CloudFormation
    Resource. (ie: Only alphanumeric characters)
    """
    alphanumeric = r'[a-zA-Z0-9]+'
    parts = re.findall(alphanumeric, name)
    return ''.join([uppercase_first_letter(part) for part in parts])


def get_bucket_location(region):
    """ Determines what region the S3 bucket should be created in.

    This is annoying - rather than creating the bucket in the region that
    you are connected to, create_bucket needs a special extra argument.

    Even worse, it uses the region for everywhere BUT us-east-1, which
    is instead blank.
    """
    if region == 'us-east-1':
        location = ''
    else:
        location = region
    return location


# TODO: perhaps make this a part of the builder?
def handle_hooks(stage, hooks, region, namespace, mappings, parameters):
    """ Used to handle pre/post_build hooks.

    These are pieces of code that we want to run before/after the builder
    builds the stacks.
    """
    if hooks:
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
                result = method(region, namespace, mappings, parameters,
                                **kwargs)
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
    else:
        logger.debug("No %s hooks defined.", stage)
