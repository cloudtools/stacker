from stacker.blueprints.rds import base


class MasterInstance(base.MasterInstance):
    ENGINE = "postgres"

    def get_engine_versions(self):
        return ['9.3.1', '9.3.2', '9.3.3', '9.3.5', '9.3.6', '9.4.1']


class ReadReplica(base.ReadReplica):
    ENGINE = "postgres"
