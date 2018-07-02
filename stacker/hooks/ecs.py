from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
# A lot of this code exists to deal w/ the broken ECS connect_to_region
# function, and will be removed once this pull request is accepted:
#   https://github.com/boto/boto/pull/3143
from past.builtins import basestring
import logging

from stacker.session_cache import get_session

logger = logging.getLogger(__name__)


def create_clusters(provider, context, **kwargs):
    """Creates ECS clusters.

    Expects a "clusters" argument, which should contain a list of cluster
    names to create.

    Args:
        provider (:class:`stacker.providers.base.BaseProvider`): provider
            instance
        context (:class:`stacker.context.Context`): context instance

    Returns: boolean for whether or not the hook succeeded.

    """
    conn = get_session(provider.region).client('ecs')

    try:
        clusters = kwargs["clusters"]
    except KeyError:
        logger.error("setup_clusters hook missing \"clusters\" argument")
        return False

    if isinstance(clusters, basestring):
        clusters = [clusters]

    cluster_info = {}
    for cluster in clusters:
        logger.debug("Creating ECS cluster: %s", cluster)
        r = conn.create_cluster(clusterName=cluster)
        cluster_info[r["cluster"]["clusterName"]] = r
    return {"clusters": cluster_info}
