import asyncio
import asyncpg
from typing import List
import pydantic
import logging
from enum import Enum
from .database_connector import DatabaseConnector
from .retry import retry

logger = logging.getLogger("webmonitor")

class DatabaseConnectorPostgresql(DatabaseConnector):
    """DB connection module to PostgreSQL.
    """

    def __init__(self, db_user: str, db_pass: str, db_name: str, db_host: str, db_port: int, db_ssl: str) -> None:
        """Constructor method.

        Lazy initialization.

        :param db_user: The username for the database connection.
        :param db_pass: The password for the database connection.
        :param db_name: Name of the database on the server.
        :param db_host: The host address of the database server.
        :param db_port: The port number on which the database server is listening.
        :param db_ssl: Indicates whether SSL should be used for the connection.
        """
        super().__init__(db_user, db_pass, db_name, db_host, db_port, db_ssl)
        self.conn_pool = None


    async def initialize(self) -> None:
        self.conn_pool = await asyncpg.create_pool(
                user=self.db_user,
                password=self.db_pass,
                database=self.db_name,
                host=self.db_host,
                port=self.db_port,
                ssl=self.db_ssl)


    async def close(self) -> None:
        await self.conn_pool.close()


    @retry(tries=5, delay=30, backoff=2, max_interval=120, logger=logger)
    async def db_fetch(self, query) -> List[dict]:
        """Runs query and returns results.

        :return: query results.
        """
        result = []
        async with self.conn_pool.acquire() as conn:
            result = await conn.fetch(query)
        return result


    @retry(tries=5, delay=30, backoff=2, max_interval=120, logger=logger)
    async def db_execute(self, query) -> None:
        """Runs query.
        """
        async with self.conn_pool.acquire() as conn:
            await conn.execute(query)


    @retry(tries=5, delay=30, backoff=2, max_interval=120, logger=logger)
    async def db_executemany(self, query, data) -> None:
        """Runs query.
        """
        async with self.conn_pool.acquire() as conn:
            await conn.executemany(query, data)


    async def fetch_version(self) -> str:
        """Returns DB version.

        :return: DB version.
        :rtype: string
        """
        query = DatabaseConnector.get_query_db_version()
        res = await self.db_fetch(query)
        res = res[0]
        return res


    async def fetch_all_from_table(self, table_name: str, cls: pydantic.BaseModel) -> List[pydantic.BaseModel]:
        """Returns all rows in table.

        :param table_name: table name
        :param cls: pydantic class object reference value.
        :return: a list of instances of cls representing the returned rows
        :rtype: list
        """
        query = DatabaseConnector.get_query_select_all(table_name)
        reply = await self.db_fetch(query)
        res = []
        for row in reply:
            row = dict(row)
            row = DatabaseConnector.row_to_pydantic(row, cls)
            res += [row]
        return res


    async def execute_create_table(self, table_name: str, obj: pydantic.BaseModel) -> None:
        """Creates a table if it doesn't exist. The rows and their type are matched to the pydantic object.

        :param table_name: table name.
        :param obj: a column will be created for each attribute in this object.
        """
        query = DatabaseConnector.get_query_create_table(table_name, obj, True)
        await self.db_execute(query)


    async def execute_drop_table(self, table_name: str) -> None:
        """Drop table.

        :param table_name: table name.
        """
        query = DatabaseConnector.get_query_drop_table(table_name)
        await self.db_execute(query)


    async def execute_insert_into_table(self, table_name: str, obj: pydantic.BaseModel) -> None:
        """Inserts the corresponding row representation of obj into a table.

        :param table_name: table name.
        :param obj: value to insert in the table.
        """
        query, data = DatabaseConnector.get_query_insert_many_into_table(table_name, [obj], True)
        await self.db_executemany(query, data)

    async def execute_insert_many_into_table(self, table_name: str, objs: List[pydantic.BaseModel]) -> None:
        """Inserts the corresponding row representation of obj into a table.

        :param table_name: table name.
        :param obj: list of object values to insert in the table.
        """
        query, data = DatabaseConnector.get_query_insert_many_into_table(table_name, objs, True)
        await self.db_executemany(query, data)

