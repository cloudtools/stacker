import logging

logger = logging.getLogger(__name__)


from aws_helper.connection import ConnectionManager

from stacker.util import create_route53_zone


def create_domain(region, namespace, mappings, parameters, **kwargs):
    conn = ConnectionManager(region)
    domain = kwargs.get('domain', parameters.get('BaseDomain'))
    if not domain:
        logger.error("domain argument or BaseDomain parameter not provided.")
        return False
    create_route53_zone(conn.route53, domain)
    return True
