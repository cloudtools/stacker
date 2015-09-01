from stacker.blueprints.rds import base


class MasterInstance(base.MasterInstance):
    ENGINE = "MySQL"

    def _get_engine_versions(self):
        return ['5.1.73a', '5.1.73b', '5.5.40', '5.5.40a', '5.5.40b', '5.5.41',
                '5.5.42', '5.6.19a', '5.6.19b', '5.6.21', '5.6.21b', '5.6.22',
                '5.6.23']


class ReadReplica(base.ReadReplica):
    ENGINE = "MySQL"