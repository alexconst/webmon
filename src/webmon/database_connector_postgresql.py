import asyncio
import asyncpg
from typing import List

class DatabasePostgresql():
    """DB connection module to PostgreSQL.
    """

    def __init__(self):
        """Constructor method.

        Uses lazy initialization, the actual initialization is done with `connect`.
        """
        self.conn = None


    async def connect(self, db_user: str, db_pass: str, db_name: str, db_host: str, db_port: int, db_ssl: str) -> None:
        """Creates a DB connection.
        
        :param db_user: The username for the database connection.
        :param db_pass: The password for the database connection.
        :param db_name: Name of the database on the server.
        :param db_host: The host address of the database server.
        :param db_port: The port number on which the database server is listening.
        :param db_ssl: Indicates whether SSL should be used for the connection.
        """
        self.conn = await asyncpg.connect(user=db_user, password=db_pass, database=db_name, host=db_host, port=db_port, ssl=db_ssl)


    async def read_query(self, query: str) -> List(dict):
        """Executes a SQL query and returns the result.

        :param query: SQL query.
        :return: Result of query.
        :rtype: list of dict elements.
        """
        tmp = await self.conn.fetch(query)
        res = [dict(elem) for elem in tmp]
        return res


    async def get_version(self) -> str:
        """Returns DB version.

        :return: DB version.
        :rtype: string
        """
        query = 'SELECT VERSION()'
        res = await self.read_query(query)
        res = res[0]
        return res

    async def write_query(self, query: str) -> None:
        """Executes one or more SQL commands at once.

        :param query: SQL query.
        """
        self.conn.execute(query)


