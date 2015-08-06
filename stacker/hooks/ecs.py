# A lot of this code exists to deal w/ the broken ECS connect_to_region
# function, and will be removed once this pull request is accepted:
#   https://github.com/boto/boto/pull/3143
import logging

logger = logging.getLogger(__name__)

from boto.regioninfo import get_regions
from boto.ec2containerservice.layer1 import EC2ContainerServiceConnection


def regions():
    return get_regions('ec2containerservice',
                       connection_cls=EC2ContainerServiceConnection)


def connect_to_region(region_name, **kw_params):
    for region in regions():
        if region.name == region_name:
            return region.connect(**kw_params)
    return None


def create_clusters(region, namespace, mappings, parameters, **kwargs):
    """Creates ECS clusters.

    Expects a 'clusters' argument, which should contain a list of cluster
    names to create.

    """
    conn = connect_to_region(region)
    try:
        clusters = kwargs['clusters']
    except KeyError:
        logger.error("setup_clusters hook missing 'clusters' argument")
        return False

    if isinstance(clusters, basestring):
        clusters = [clusters]

    for cluster in clusters:
        logger.debug("Creating ECS cluster: %s", cluster)
        conn.create_cluster(cluster)
    return True
