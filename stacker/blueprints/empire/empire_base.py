import logging

logger = logging.getLogger(__name__)

from troposphere import Base64, Join

from stacker.blueprints.base import Blueprint


class EmpireBase(Blueprint):
    def create_conditions(self):
        logger.debug("No conditions to setup for %s", self.name)

    def create_security_groups(self):
        logger.debug("No security_groups to setup for %s", self.name)

    def create_ecs_cluster(self):
        logger.debug("No ecs cluster to setup for %s", self.name)

    def create_load_balancer(self):
        logger.debug("No load_balancer to setup for %s", self.name)

    def create_iam_profile(self):
        logger.debug("No iam_profile to setup for %s", self.name)

    def create_autoscaling_group(self):
        logger.debug("No autoscaling_group to setup for %s", self.name)

    def generate_user_data(self):
        contents = Join("", self.generate_seed_contents())
        stanza = Base64(Join(
            "",
            [
                "#cloud-config\n",
                "write_files:\n",
                "  - encoding: b64\n",
                "    content: ", Base64(contents), "\n",
                "    owner: root:root\n",
                "    path: /etc/empire/seed\n",
                "    permissions: 0640\n"
            ]
        ))
        return stanza

    def create_template(self):
        self.create_conditions()
        self.create_security_groups()
        self.create_ecs_cluster()
        self.create_load_balancer()
        self.create_iam_profile()
        self.create_autoscaling_group()
