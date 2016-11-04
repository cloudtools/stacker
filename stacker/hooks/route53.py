import logging

import boto3

from stacker.util import create_route53_zone

logger = logging.getLogger(__name__)


def create_domain(region, namespace, mappings, parameters, **kwargs):
    client = boto3.client("route53", region_name=region)
    domain = kwargs.get('domain', parameters.get('BaseDomain'))
    if not domain:
        logger.error("domain argument or BaseDomain parameter not provided.")
        return False
    create_route53_zone(client, domain)
    return True
