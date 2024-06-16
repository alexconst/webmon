import asyncio
import logging
from collections import OrderedDict
from enum import Enum
from typing import Any, Dict, Tuple, List

import asyncpg
import pydantic

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

    async def open(self) -> None:
        self.conn_pool = await asyncpg.create_pool(user=self.db_user,
                                                   password=self.db_pass,
                                                   database=self.db_name,
                                                   host=self.db_host,
                                                   port=self.db_port,
                                                   ssl=self.db_ssl)

    async def close(self) -> None:
        await self.conn_pool.close() # type: ignore

    @retry(tries=5, delay=30, backoff=2, max_interval=120, logger=logger)
    async def db_fetch(self, query: str) -> List[dict]:
        """Runs query and returns results.

        :return: query results.
        """
        result = []
        async with self.conn_pool.acquire() as conn: # type: ignore
            result = await conn.fetch(query)
        return result

    @retry(tries=5, delay=30, backoff=2, max_interval=120, logger=logger)
    async def db_execute(self, query: str) -> None:
        """Runs query.
        """
        async with self.conn_pool.acquire() as conn: # type: ignore
            await conn.execute(query)

    @retry(tries=5, delay=30, backoff=2, max_interval=120, logger=logger)
    async def db_executemany(self, query: str, data: dict) -> None:
        """Runs query.
        """
        async with self.conn_pool.acquire() as conn: # type: ignore
            await conn.executemany(query, data)

    async def fetch_version(self) -> str:
        """Returns DB version.

        :return: DB version.
        :rtype: string
        """
        query = DatabaseConnectorPostgresql.get_query_db_version()
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
        query = DatabaseConnectorPostgresql.get_query_select_all(table_name)
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
        query = DatabaseConnectorPostgresql.get_query_create_table(table_name, obj, True)
        await self.db_execute(query)

    async def execute_drop_table(self, table_name: str) -> None:
        """Drop table.

        :param table_name: table name.
        """
        query = DatabaseConnectorPostgresql.get_query_drop_table(table_name)
        await self.db_execute(query)

    async def execute_insert_into_table(self, table_name: str, obj: pydantic.BaseModel) -> None:
        """Inserts the corresponding row representation of obj into a table.

        :param table_name: table name.
        :param obj: value to insert in the table.
        """
        query, data = DatabaseConnectorPostgresql.get_query_insert_many_into_table(table_name, [obj], True)
        await self.db_executemany(query, data)

    async def execute_insert_many_into_table(self, table_name: str, objs: List[pydantic.BaseModel]) -> None:
        """Inserts the corresponding row representation of obj into a table.

        :param table_name: table name.
        :param obj: list of object values to insert in the table.
        """
        query, data = DatabaseConnectorPostgresql.get_query_insert_many_into_table(table_name, objs, True)
        await self.db_executemany(query, data)

    @staticmethod
    def get_query_create_table(table_name: str, obj: pydantic.BaseModel, use_name_hints: bool) -> str:
        """Generate SQL query to create table. The rows and their type are matched to the pydantic object.

        :param table_name: table name.
        :param obj: a column will be created for each attribute in this object.
        :param use_name_hints: if True it will use the field name to set column properties:
            If the field name matches string `id` or ends in substring `_id` then it sets the column as primary key.
            If the field name ends in substring `_uq` then it sets the column as unique.
        :return: SQL query.
        :rtype: string
        """
        mappings = {
            'int': 'INT',
            'integer': 'INT',
            'number': 'FLOAT',
            'float': 'FLOAT',
            'enum': 'INT',
            'str': 'TEXT',
            'string': 'TEXT',
            'datetime': 'DATETIME'
        }
        query = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        schema_dict = obj.model_json_schema()
        primary_key = ''
        for key, value in schema_dict["properties"].items():
            if issubclass(obj.__annotations__[key], Enum) or isinstance(obj.__annotations__[key], Enum):
                value = mappings['int']
            else:
                value = mappings[value['type']]
            if use_name_hints and (key == 'id' or key.endswith('_id')):
                query += f"{key} SERIAL,\n"
                primary_key = f",\nPRIMARY KEY ({key})\n"
            elif use_name_hints and (key.endswith('_uq')):
                query += f"{key} {value} UNIQUE,\n"
            else:
                query += f"{key} {value},\n"
        query = query[:-2] + primary_key + ");"
        return query

    @staticmethod
    def get_query_drop_table(table_name: str) -> str:
        """Drop table.

        :param table_name: table name.
        :return: SQL query.
        :rtype: string
        """
        query = f"DROP TABLE IF EXISTS {table_name};"
        return query

    @staticmethod
    def get_query_insert_many_into_table(table_name: str, objs: List[pydantic.BaseModel], use_name_hints: bool) -> Tuple[str, List[Tuple[Any, ...]]]:
        """Generate SQL query to insert row into table. The new row will match the pydantic object.

        :param table_name: table name.
        :param objs: list of objects to be converted and inserted as a row.
        :param use_name_hints: if True it will handle some fields in a special form
            If the name is either `id` or ending with substring `_id` then it will ignore it (ie primary key).
            If the name ends in substring `_uq` then the query will set to ignore conflicts.
        :return: a tuple with the SQL query and the data.
        :rtype: tuple(string, dict)
        """

        query_template = 'INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) {conflict_expression};'
        rows = []
        for obj in objs:
            columns = []
            columns_conflict = []
            placeholders = []
            row = OrderedDict()
            data = obj.model_dump(exclude_unset=True)
            # convert any enum fields to integers
            for key, value in data.items():
                if isinstance(value, Enum):
                    data[key] = int(value.value)
            # process all fields
            for key, value in data.items():
                if use_name_hints and (key == "id" or key.endswith("_id")):
                    continue
                elif use_name_hints and key.endswith("_uq"):
                    columns.append(key)
                    columns_conflict.append(key)
                    placeholders.append(f"${len(columns)}")
                    row[key] = value
                else:
                    columns.append(key)
                    placeholders.append(f"${len(columns)}")
                    row[key] = value
            rows.append(tuple(row.values()))
        # construct the query
        columns_str = ', '.join(columns)
        placeholders_str = ', '.join(placeholders)
        conflict_expression = f"ON CONFLICT ({', '.join(columns_conflict)}) DO NOTHING" if columns_conflict else ""
        query = query_template.format(table_name=table_name,
                                      columns=columns_str,
                                      placeholders=placeholders_str,
                                      conflict_expression=conflict_expression)
        return query, rows

    @staticmethod
    def get_query_db_version() -> str:
        """Generate SQL query to get the DB version.

        :return: SQL query.
        :rtype: string
        """
        query = 'SELECT VERSION()'
        return query

    @staticmethod
    def get_query_select_all(table_name: str) -> str:
        """Generate SQL query to get all rows from table.

        :param table_name: table name
        :return: SQL query.
        :rtype: string
        """
        query = f'SELECT * FROM {table_name}'
        return query
