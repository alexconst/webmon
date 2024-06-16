from abc import ABC, abstractmethod
from enum import Enum
from typing import List

import pydantic


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

    @abstractmethod
    async def open(self):
        raise NotImplementedError

    @abstractmethod
    async def close(self):
        raise NotImplementedError

    @abstractmethod
    async def execute_create_table(self, table_name: str, obj: pydantic.BaseModel) -> None:
        raise NotImplementedError

    @abstractmethod
    async def execute_drop_table(self, table_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def execute_insert_many_into_table(self, table_name: str, objs: List[pydantic.BaseModel]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def fetch_all_from_table(self, table_name: str, cls: pydantic.BaseModel) -> List[pydantic.BaseModel]:
        raise NotImplementedError

    @staticmethod
    def row_to_pydantic(row: dict, cls: pydantic.BaseModel) -> pydantic.BaseModel:
        """Convert a row representation to a given pydantic object.
        Required because pydantic doesn't accept None values.

        If a value is None then it will be initialized as follows:
            If of type string then to ''
            If of type int then to 0

        :param row: dict representation of the row.
        :param cls: pydantic class object reference value.
        :return: instance of the parameter class with values set to the ones in row.
        :rtype: pydantic.BaseModel
        """
        schema_dict = cls.model_json_schema()["properties"]
        for key, val in row.items():
            if val is None:
                valtype = schema_dict[key]['type']
                if valtype == 'string':
                    row[key] = ''
                elif valtype == 'integer':
                    row[key] = 0
        res = cls.model_validate(row)
        return res
