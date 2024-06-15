from typing import List
from abc import ABC, abstractmethod
import pydantic
from enum import Enum
from collections import OrderedDict


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
    async def db_fetch(self, query: str) -> List[dict]:
        raise NotImplementedError


    @abstractmethod
    async def db_execute(self, query: str) -> None:
        raise NotImplementedError


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
        mappings = {'int': 'INT', 'integer': 'INT', 'number': 'FLOAT', 'float': 'FLOAT', 'enum': 'INT', 'str': 'TEXT', 'string': 'TEXT', 'datetime': 'DATETIME'}
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
    def get_query_insert_into_table(table_name: str, obj: pydantic.BaseModel, use_name_hints: bool) -> str:
        """Generate SQL query to insert row into table. The new row will match the pydantic object.

        :param table_name: table name.
        :param obj: values to be inserted as a row.
        :param use_name_hints: if True it will handle some fields in a special form
            If the name is either `id` or ending with substring `_id` then it will ignore it (ie primary key).
            If the name ends in substring `_uq` then the query will set to ignore conflicts.
        :return: SQL query.
        :rtype: string
        """

        def sanitize(s: str):
            s = s.replace("'", "''")
            s = s.replace('"', '""')
            s = s.replace('\\', '\\\\')
            return s

        query = f"INSERT INTO {table_name} ("
        schema_dict = obj.model_json_schema()
        values = "VALUES ("
        conflict_head = 'ON CONFLICT ('
        conflict_mid = ''
        conflict_tail = ') DO NOTHING;'
        for key, _ in schema_dict["properties"].items():
            val = obj.model_dump()[key]
            if use_name_hints and (key == 'id' or key.endswith('_id')):
                continue
            if use_name_hints and key.endswith('_uq'):
                if conflict_mid:
                    conflict_mid += f',{key}'
                else:
                    conflict_mid = key
            if not val:
                # skip empty strings
                continue
            query += f"{key}, "
            if isinstance(val, str):
                val = sanitize(val)
                values += f"'{val}', "
            elif issubclass(val.__class__, Enum) or isinstance(val, Enum):
                values += f"{str(val.value)}, "
            else:
                values += f"{str(val)}, "
        query = query[:-2] + ') ' + values[:-2] + ');'
        if conflict_mid:
            query = query[:-1] + f' {conflict_head}{conflict_mid}{conflict_tail}'
        return query


    @staticmethod
    def get_querypair_insert_many_into_table(table_name: str, objs: List[pydantic.BaseModel], use_name_hints: bool) -> (str, dict):
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
#                    row.append(f"${len(columns)}")
#            row = ', '.join(row)
#            placeholders.append(row)
            rows.append(tuple(row.values()))
        # construct the query
        columns_str = ', '.join(columns)
        placeholders_str = ', '.join(placeholders)
        conflict_expression = f"ON CONFLICT ({', '.join(columns_conflict)}) DO NOTHING" if columns_conflict else ""
        query = query_template.format(table_name=table_name, columns=columns_str, placeholders=placeholders_str, conflict_expression=conflict_expression)
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


