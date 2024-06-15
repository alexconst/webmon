from enum import Enum
from types import SimpleNamespace
import asyncio
from .database_connector_postgresql import DatabaseConnectorPostgresql

class DatabaseType(Enum):
    POSTGRESQL = 100

class DatabaseConnectorFactory():

    def __init__(self, db_type: DatabaseType, db_config: dict):
        self.db_type = db_type
        self.db_config = db_config

    async def get_connector(self) -> "DatabaseConnector":
        cfg = SimpleNamespace(**{k: v for k, v in self.db_config.items()})
        if self.db_type == DatabaseType.POSTGRESQL:
            dbc = DatabaseConnectorPostgresql(cfg.db_user, cfg.db_pass, cfg.db_name, cfg.db_host, cfg.db_port, cfg.db_ssl)
        else:
            raise NotImplementedError
        return dbc

