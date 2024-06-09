from enum import Enum
from typing import List

class DatabaseType(Enum):
    POSTGRESQL = "postgresql"


class DatabaseConnector:
    """Abstraction layer for DB connections.
    """

    def __init__(self, db_type: DatabaseType, db_user: str, db_pass: str, db_name: str, db_host: str, db_port: int, db_ssl: str) -> None:
        """Constructor method.

        Saves database config details.
        Uses lazy initialization, the actual initialization is done with `connect`.
        
        :param db_type: The type of database to connect to.
        :param db_user: The username for the database connection.
        :param db_pass: The password for the database connection.
        :param db_name: Name of the database on the server.
        :param db_host: The host address of the database server.
        :param db_port: The port number on which the database server is listening.
        :param db_ssl: Indicates whether SSL should be used for the connection.
        """
        self.db_type = db_type
        self.db_user = db_user
        self.db_pass = db_pass
        self.db_name = db_name
        self.db_host = db_host
        self.db_port = db_port
        self.db_ssl = db_ssl
        self.db = None


    async def connect(self) -> None:
        """Establishes a connection to the database based on the db_type attribute.
        """
        if self.db_type == DatabaseType.POSTGRESQL:
            self.db = DatabasePostgresql()
            self.db.connect(self.db_user, self.db_pass, self.db_name, self.db_host, self.db_port, db_ssl)
        else:
            raise NotImplementedError


    async def read_query(self, query: str) -> List[dict]:
        """Executes a SQL query and returns the result.

        :param query: SQL query.
        :return: Result of query.
        :rtype: list of dict elements.
        """
        return self.db.read_query(query)


    async def write_query(self, query: str) -> None:
        """Executes one or more SQL commands at once.

        :param query: SQL query.
        """
        self.db.write_query(query)


