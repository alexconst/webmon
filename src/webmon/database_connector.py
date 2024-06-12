from typing import List
from abc import ABC, abstractmethod
import pydantic
from enum import Enum


class DatabaseConnector:
    """Abstraction layer for DB connections.
    """

    def __init__(self, db_user: str, db_pass: str, db_name: str, db_host: str, db_port: int, db_ssl: str) -> None:
        """Constructor method.

        Saves database config details. Doesnt't perform any connect.
        
        :param db_user: The username for the database connection.
        :param db_pass: The password for the database connection.
        :param db_name: Name of the database on the server.
        :param db_host: The host address of the database server.
        :param db_port: The port number on which the database server is listening.
        :param db_ssl: Indicates whether SSL should be used for the connection.
        """
        self.db_user = db_user
        self.db_pass = db_pass
        self.db_name = db_name
        self.db_host = db_host
        self.db_port = db_port
        self.db_ssl = db_ssl
        #self.db = None


    @abstractmethod
    async def db_fetch(self, query: str) -> List[dict]:
        raise NotImplementedError


    @abstractmethod
    async def db_execute(self, query: str) -> None:
        raise NotImplementedError


    @staticmethod
    def get_query_create_table(table_name: str, obj: pydantic.BaseModel, use_id_as_primary: bool) -> str:
        """Generate SQL query to create table. The rows and their type are matched to the pydantic object.

        :param table_name: table name.
        :param obj: a column will be created for each attribute in this object.
        :param use_id_as_primary: if True it will use the field with string `id` or ending substring `_id` as primary key.
        :return: SQL query.
        :rtype: string
        """
        mappings = {'int': 'INT', 'integer': 'INT', 'number': 'FLOAT', 'float': 'FLOAT', 'enum': 'INT', 'str': 'TEXT', 'string': 'TEXT', 'datetime': 'DATETIME'}
        query = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
        schema_dict = obj.model_json_schema()
        primary_key = ''
        for key, value in schema_dict["properties"].items():
            if issubclass(obj.__annotations__[key], Enum) or isinstance(obj.__annotations__[key], Enum):
                value = mappings['int']
            else:
                value = mappings[value['type']]
            if use_id_as_primary and (key == 'id' or key.endswith('_id')):
                query += f"{key} SERIAL,\n"
                primary_key = f",\nPRIMARY KEY ({key})\n"
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
    def get_query_insert_into_table(table_name: str, obj: pydantic.BaseModel, skip_id_attrs: bool) -> str:
        """Generate SQL query to insert row into table. The new row will match the pydantic object.

        :param table_name: table name.
        :param obj: values to be inserted as a row.
        :param skip_id_attrs: if True then it will ignore attributes whose name are either `id` or ending with substring `_id`
        :return: SQL query.
        :rtype: string
        """
        query = f"INSERT INTO {table_name} ("
        schema_dict = obj.model_json_schema()
        values = "VALUES ("
        for key, _ in schema_dict["properties"].items():
            val = obj.model_dump()[key]
            if skip_id_attrs and (key == 'id' or key.endswith('_id')):
                continue
            if not val:
                # skip empty strings
                continue
            query += f"{key}, "
            if isinstance(val, str):
                values += f"'{val}', "
            elif issubclass(val.__class__, Enum) or isinstance(val, Enum):
                values += f"{str(val.value)}, "
            else:
                values += f"{str(val)}, "
        query = query[:-2] + ') ' + values[:-2] + ')'
        return query


    @staticmethod
    def get_query_db_version() -> str:
        """Generate SQL query to get the DB version.

        :return: SQL query.
        :rtype: string
        """
        query = 'SELECT VERSION()'
        return query



#    async def connect(self) -> None:
#        """Establishes a connection to the database based on the db_type attribute.
#        """
#        if self.db_type == DatabaseType.POSTGRESQL.value:
#            self.db = DatabasePostgresql()
#            await self.db.connect(self.db_user, self.db_pass, self.db_name, self.db_host, self.db_port, self.db_ssl)
#        else:
#            raise NotImplementedError
#
#
#    async def read_query(self, query: str) -> List[dict]:
#        """Executes a SQL query and returns the result.
#
#        :param query: SQL query.
#        :return: Result of query.
#        :rtype: list of dict elements.
#        """
#        return self.db.read_query(query)
#
#
#    async def write_query(self, query: str) -> None:
#        """Executes one or more SQL commands at once.
#
#        :param query: SQL query.
#        """
#        self.db.write_query(query)
#
#
#    async def create_table(self, table_name: str, obj: object) -> None:
#        await self.db.create_table(table_name, obj)
#
#
#    async def drop_table(self, table_name: str) -> None:
#        await self.db.drop_table(table_name)
#
#
#    async def insert_into_table(self, table_name: str, obj: object) -> None:
#        await self.db.insert_into_table(table_name, obj)
#
#

