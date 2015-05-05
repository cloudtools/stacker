import logging

logger = logging.getLogger(__name__)


from aws_helper.connection import ConnectionManager

from stacker.util import create_route53_zone


def create_domain(region, namespace, mappings, parameters, **kwargs):
    conn = ConnectionManager(region)
    try:
        domain = parameters['BaseDomain']
    except KeyError:
        logger.error("BaseDomain parameter not provided.")
        return False
    create_route53_zone(conn.route53, domain)
    return True
