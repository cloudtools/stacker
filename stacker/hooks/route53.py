import logging

import boto3

from stacker.util import create_route53_zone

logger = logging.getLogger(__name__)


def create_domain(provider, context, **kwargs):
    """Create a domain within route53.

    Args:
        provider (:class:`stacker.providers.base.BaseProvider`): provider
            instance
        context (:class:`stacker.context.Context`): context instance

    Returns: boolean for whether or not the hook succeeded.

    """
    client = boto3.client("route53", region_name=provider.region)
    domain = kwargs.get("domain", context.parameters.get("BaseDomain"))
    if not domain:
        logger.error("domain argument or BaseDomain parameter not provided.")
        return False
    create_route53_zone(client, domain)
    return True
