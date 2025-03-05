import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/'))
import asyncio
import json
from types import SimpleNamespace

import pytest

from webmon.database_connector_postgresql import DatabaseConnectorPostgresql
from webmon.website import Website

# uncomment if debugging:
#import logging
#logging.getLogger("webmonitor").setLevel(logging.DEBUG)


@pytest.mark.asyncio(loop_scope="class")
class TestDatabaseConnectorPostgresql:
    loop: asyncio.AbstractEventLoop

    db = None
    test_table_name = 'test_table'

    async def setup(self):
        test_db_config = os.path.join(os.path.dirname(__file__), '../../secrets/test_db_postgresql.json')
        with open(test_db_config, 'r') as file:
            test_db_config = json.load(file)
        cfg = SimpleNamespace(**{k: v for k, v in test_db_config.items()})
        TestDatabaseConnectorPostgresql.db = DatabaseConnectorPostgresql(cfg.db_user, cfg.db_pass, cfg.db_name, cfg.db_host, cfg.db_port, cfg.db_ssl)
        await TestDatabaseConnectorPostgresql.db.open()

    async def test_fetch_version(self):
        if not TestDatabaseConnectorPostgresql.db:
            await self.setup()
        res = await TestDatabaseConnectorPostgresql.db.fetch_version()
        assert 'PostgreSQL' in res[0]
        assert 'compiled by gcc' in res[0]

    async def test_execute_table_lifecycle(self):
        if not TestDatabaseConnectorPostgresql.db:
            await self.setup()
        table_name = TestDatabaseConnectorPostgresql.test_table_name
        website = Website(website_id=-1, url_uq='https://foo.bar', interval=5, regex='')
        query = f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table_name}'"

        try:
            res = await TestDatabaseConnectorPostgresql.db.db_fetch(query)
            assert str(res[0]) == '<Record count=0>'

            await TestDatabaseConnectorPostgresql.db.execute_create_table(table_name, website)
            res = await TestDatabaseConnectorPostgresql.db.db_fetch(query)
            assert str(res[0]) == '<Record count=1>'

            await TestDatabaseConnectorPostgresql.db.execute_drop_table(table_name)
            res = await TestDatabaseConnectorPostgresql.db.db_fetch(query)
            assert str(res[0]) == '<Record count=0>'

        finally:
            # clean up any failed test
            await TestDatabaseConnectorPostgresql.db.execute_drop_table(table_name)

    async def test_execute_insert_table(self):
        if not TestDatabaseConnectorPostgresql.db:
            await self.setup()
        table_name = TestDatabaseConnectorPostgresql.test_table_name
        website1 = Website(website_id=-1, url_uq='https://foo.bar', interval=5, regex='')
        website2 = Website(website_id=-1, url_uq='https://matrix.bar', interval=10, regex='neo')
        query_count = f"SELECT COUNT(*) FROM {table_name}"
        query_elem = f"SELECT * FROM {table_name} WHERE interval = 10"

        try:
            await TestDatabaseConnectorPostgresql.db.execute_create_table(table_name, website1)
            # assert values can be inserted
            await TestDatabaseConnectorPostgresql.db.execute_insert_into_table(table_name, website1)
            await TestDatabaseConnectorPostgresql.db.execute_insert_into_table(table_name, website2)
            res = await TestDatabaseConnectorPostgresql.db.db_fetch(query_count)
            assert str(res[0]) == '<Record count=2>'
            # assert primary key auto increments
            res = await TestDatabaseConnectorPostgresql.db.db_fetch(query_elem)
            assert res[0].get('website_id') == 2
            assert res[0].get('url_uq') == 'https://matrix.bar'
        finally:
            # clean up
            await TestDatabaseConnectorPostgresql.db.execute_drop_table(table_name)

    async def test_execute_insert_table_and_fetch_all(self):
        if not TestDatabaseConnectorPostgresql.db:
            await self.setup()
        table_name = TestDatabaseConnectorPostgresql.test_table_name
        website1 = Website(website_id=1, url_uq='https://foo.bar', interval=5, regex='')
        website2 = Website(website_id=2, url_uq='https://matrix.bar', interval=10, regex='neo')
        try:
            # setup
            await TestDatabaseConnectorPostgresql.db.execute_create_table(table_name, website1)
            await TestDatabaseConnectorPostgresql.db.execute_insert_into_table(table_name, website1)
            await TestDatabaseConnectorPostgresql.db.execute_insert_into_table(table_name, website2)
            # test
            res = await TestDatabaseConnectorPostgresql.db.fetch_all_from_table(table_name, Website)
            # assert
            assert res[0] == website1
            assert res[1] == website2
        finally:
            # clean up
            await TestDatabaseConnectorPostgresql.db.execute_drop_table(table_name)

    async def test_execute_insert_many_table(self):
        if not TestDatabaseConnectorPostgresql.db:
            await self.setup()
        table_name = TestDatabaseConnectorPostgresql.test_table_name
        website1 = Website(website_id=1, url_uq='https://foo.bar', interval=5, regex='')
        website2 = Website(website_id=2, url_uq='https://matrix.bar', interval=10, regex='neo')
        websites = [website1, website2]
        try:
            # setup
            await TestDatabaseConnectorPostgresql.db.execute_create_table(table_name, website1)
            await TestDatabaseConnectorPostgresql.db.execute_insert_many_into_table(table_name, websites)
            # test
            res = await TestDatabaseConnectorPostgresql.db.fetch_all_from_table(table_name, Website)
            # assert
            assert res[0] == website1
            assert res[1] == website2
        finally:
            # clean up
            await TestDatabaseConnectorPostgresql.db.execute_drop_table(table_name)
