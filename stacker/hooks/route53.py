import logging

logger = logging.getLogger(__name__)

from boto.route53 import connect_to_region

from stacker.util import create_route53_zone


def create_domain(region, namespace, mappings, parameters, **kwargs):
    conn = connect_to_region(region)
    domain = kwargs.get('domain', parameters.get('BaseDomain'))
    if not domain:
        logger.error("domain argument or BaseDomain parameter not provided.")
        return False
    create_route53_zone(conn, domain)
    return True
