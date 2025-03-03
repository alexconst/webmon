import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../src/'))
import asyncio
import json

import pytest

from webmon.database_connector_factory import DatabaseConnectorFactory, DatabaseType
from webmon.healthcheck import Healthcheck
from webmon.web_monitor import WebMonitor


@pytest.mark.asyncio(loop_scope="class")
class TestWebMonitor:
    loop: asyncio.AbstractEventLoop

    wm = None

    def setup(self):
        dbconfig_filename = os.path.join(os.path.dirname(__file__), '../secrets/test_db_postgresql.json')
        sites_filename = os.path.join(os.path.dirname(__file__), '../data/websites_top3.csv')
        number_healthchecks = 1
        TestWebMonitor.wm = WebMonitor(dbconfig_filename, sites_filename, number_healthchecks)
        TestWebMonitor.wm.tablename_website = 'test_table_website'
        TestWebMonitor.wm.tablename_healthcheck = 'test_table_healthcheck'

    async def test_run(self):
        # run 1
        self.setup()
        await TestWebMonitor.wm.run('drop-tables')
        # run 2
        self.setup()
        await TestWebMonitor.wm.run('monitor')

        # prepare
        self.setup()
        with open(TestWebMonitor.wm.db_config, 'r') as file:
            TestWebMonitor.wm.db_config = json.load(file)
        db_type = DatabaseType[TestWebMonitor.wm.db_config['db_type'].upper()]
        TestWebMonitor.wm.dbc = await DatabaseConnectorFactory(db_type, TestWebMonitor.wm.db_config).get_connector()
        await TestWebMonitor.wm.dbc.open()
        res = await TestWebMonitor.wm.dbc.fetch_all_from_table(TestWebMonitor.wm.tablename_healthcheck, Healthcheck)

        # test
        assert len(res) == 3
        for idx, check in enumerate(res):
            assert check.http_status_code == 200

        # cleanup
        await TestWebMonitor.wm._finish()
        self.setup()
        await TestWebMonitor.wm.run('drop-tables')
