from stacker.blueprints.rds import base


class PostgresMixin(object):
    def engine(self):
        return "postgres"

    def get_engine_versions(self):
        return ['9.3.1', '9.3.2', '9.3.3', '9.3.5', '9.3.6', '9.3.9',
                '9.3.10', '9.4.1', '9.4.4', '9.4.5']

    def get_db_families(self):
        return ["postgres9.3", "postgres9.4"]


class MasterInstance(PostgresMixin, base.MasterInstance):
    pass


class ReadReplica(PostgresMixin, base.ReadReplica):
    pass
