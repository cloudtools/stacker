import logging

from stacker.session_cache import get_session

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
    session = get_session(provider.region)
    client = session.client("route53")
    domain = kwargs.get("domain")
    if not domain:
        logger.error("domain argument or BaseDomain variable not provided.")
        return False
    zone_id = create_route53_zone(client, domain)
    return {"domain": domain, "zone_id": zone_id}
