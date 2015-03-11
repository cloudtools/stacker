import logging

logger = logging.getLogger(__name__)

import time
import re
import importlib
import sys

from boto.exception import EC2ResponseError
from boto.route53.record import ResourceRecordSets


def find_subnetable_zones(conn):
    """ Using an AWS VPC Connection object determine which AZs are allowed.

    Unfortunately AWS doesn't provide a way to determine which AZs are
    actually allowed in a VPC via a simple API call.  This function does so
    by creating a VPC then trying to create a subnet in each zone.
    """
    all_zones = [zone.name for zone in conn.get_all_zones()]
    good_zones = []
    vpc = conn.create_vpc('192.168.0.0/16')
    try:
        for i, zone in enumerate(all_zones):
            try:
                subnet = conn.create_subnet(
                    vpc.id, '192.168.%d.0/24' % (i), zone)
                conn.delete_subnet(subnet.id)
                good_zones.append(zone)
            except EC2ResponseError, e:
                if ('Subnets can currently only be created in the following '
                        'availability zones:') in e.body:
                    continue
                raise
    finally:
        conn.delete_vpc(vpc.id)
    logger.debug("Subnettable zones: %s", ', '.join(good_zones))
    return good_zones


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


def cf_safe_name(name):
    """ Given a string, returns a name that is safe for use as a CloudFormation
    Resource. (ie: Only alphanumeric characters)
    """
    alphanumeric = r'[a-zA-Z0-9]+'
    parts = re.findall(alphanumeric, name)
    return ''.join([part.capitalize() for part in parts])
