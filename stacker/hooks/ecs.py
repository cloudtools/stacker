import logging

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
    conn = provider.ecs

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
