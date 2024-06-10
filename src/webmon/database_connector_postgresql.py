import asyncio
import asyncpg
from typing import List
import pydantic
import logging
from enum import Enum

logger = logging.getLogger("webmonitor")

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


    async def read_query(self, query: str) -> List[dict]:
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
        await self.conn.execute(query)


    async def create_table(self, table_name: str, obj: pydantic.BaseModel) -> None:
        """Creates a table if it doesn't exist. The rows and their type are matched to the pydantic object.
        """
        mappings = {'int': 'INT', 'integer': 'INT', 'number': 'INT', 'float': 'FLOAT', 'enum': 'INT', 'str': 'TEXT', 'string': 'TEXT', 'datetime': 'DATETIME'}
        query = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        schema_dict = obj.schema()
        for key, value in schema_dict["properties"].items():
            if issubclass(obj.__annotations__[key], Enum) or isinstance(obj.__annotations__[key], Enum):
                value = mappings['int']
            else:
                value = mappings[value['type']]
            query += f"{key} {value},\n"
        query = query[:-2] + ");"
        logger.info(f"Will create a table with this SQL query: {query}")
        await self.write_query(query)


    async def drop_table(self, table_name: str) -> None:
        query = f"DROP TABLE IF EXISTS {table_name};"
        await self.write_query(query)


    async def insert_into_table(self, table_name: str, obj: pydantic.BaseModel) -> None:
        query = f"INSERT INTO {table_name} ("
        schema_dict = obj.schema()
        values = "VALUES ("
        for key, _ in schema_dict["properties"].items():
            query += f"{key}, "
            if isinstance(obj.dict()[key], str):
                values += f"{obj.dict()[key]}"
            else:
                values += obj.dict()[key]
        values = values[:-2]
        query = query[:-2] + ")" + values
        logger.info(f"Will insert into table {table_name} with this SQL query: {query}")
        await self.write_query(query)


