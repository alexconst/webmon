import asyncio
from aiohttp import ClientSession
import csv
import json
import re
import logging
from types import SimpleNamespace
from typing import List, Optional
import time
from .database_connector_factory import DatabaseConnectorFactory, DatabaseType
from .website import Website
from .healthcheck import Healthcheck, RegexMatchStatus
import ipdb
import sys
import os

logger = logging.getLogger("webmonitor")

class WebMonitor:
    """Monitors health status of websites and saves results to a DB.
    """

    def __init__(self, db_config: str, site_list: str, num_checks: int):
        """Constructor. Lazy initialization.

        :param db_config: filename with DB config
        :param site_list: filename with list of websites to check
        :param num_checks: how many checks to perform per website before finishing. Use -1 for infinite.
        """
        self.db_config = db_config          # after proper init it will be a map with the DB config
        self.site_list = site_list          # after proper init it will be a list of website healthcheck rules
        self.tablename_website = 'website'
        self.tablename_healthcheck = 'healthcheck'
        self.num_checks = num_checks
        self.dbc = None                     # DB connector


    async def run(self, action: str):
        """Main entry point. Performs selected action.

        :param action: supported values: monitor, drop-tables.
            If 'monitor' then it performs required initialization and then monitors websites health.
            If 'drop-tables' it drops the tables used for websites and healthchecks.
        """
        if action == 'monitor':
            await self._initialize()
            await self._monitor()
        elif action == 'drop-tables':
            await self._drop_tables()
        else:
            logging.fatal(f'Invalid action: ${action}')
        await self._finish()


    async def _finish(self):
        await self.dbc.close()


    async def _drop_tables(self):
        self._read_config()
        db_type = DatabaseType[self.db_config['db_type'].upper()]
        self.dbc = await DatabaseConnectorFactory(db_type, self.db_config).get_connector()
        await self.dbc.execute_drop_table(self.tablename_healthcheck)
        await self.dbc.execute_drop_table(self.tablename_website)


    async def _initialize(self) -> None:
        """Read DB config. Read list of websites to check. Start connection to DB.
        """
        # read DB config
        self._read_config()
        # init DB
        db_type = DatabaseType[self.db_config['db_type'].upper()]
        self.dbc = await DatabaseConnectorFactory(db_type, self.db_config).get_connector()
        await self._db_init()
        # if a website list was provided then read it and setup the DB
        if self.site_list.endswith('.csv') and os.path.exists(self.site_list):
            self._read_sites_from_file()
            await self.dbc.execute_create_table(self.tablename_website, Website)
            for website in self.site_list:
                await self._db_insert_website_entry(website)
        else:
            logger.error(f"Invalid file provided. Either file doesn't exist or it doesn't have a .csv extension: {self.site_list}")
            await self._finish()
            sys.exit(1)
        # always read website list from the DB (either due to user option, or just to have website_id info as per the DB)
        await self._read_sites_from_db()


    def _read_config(self) -> None:
        """Read DB config.
        """
        with open(self.db_config, 'r') as file:
            self.db_config = json.load(file)


    def _read_sites_from_file(self) -> None:
        """Read list of websites to perform health checks from a CSV file.
        """
        delimiter = ','
        split_row = lambda row: (row[0], row[1], row[2]) if len(row)==3 else (row[0], row[1], '')
        sites = []
        with open(self.site_list, 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=delimiter)
            for idx, row in enumerate(csv_reader):
                if not row: # skip blank lines
                    continue
                if idx == 0 and f'host{delimiter}interval' in str(row):
                    continue
                url, interval, regex = split_row(row)
                url = WebMonitor.get_valid_url(url)
                sites.append(Website(website_id=-1, url_uq=url, interval=interval, regex=regex))
        self.site_list = sites


    @staticmethod
    def get_valid_url(url: str):
        """Receives a malformed url and returns a well formed one.
        """
        url_regex = '(?P<protocol>http.*://)?(?P<host>[^:/ ]+).?(?P<port>[0-9]*)/?(?P<path>.*)'
        m = re.search(url_regex, url)
        protocol = m.group('protocol')
        host = m.group('host')
        port = m.group('port')
        path = m.group('path')
        if not port and not protocol:
            protocol = 'https'
            port = 443
        elif not protocol and port:
            if port == 443:
                protocol = 'https'
            else:
                protocol = 'http'
        elif protocol and not port:
            if protocol == 'https':
                port = 443
            else:
                port = 80
        url = f'{protocol}://{host}:{port}/{path}'.rstrip('/')
        return url


    async def _read_sites_from_db(self) -> None:
        """Read list of websites to perform health checks from the DB.
        """
        res = await self.dbc.fetch_all_from_table(self.tablename_website, Website)
        self.site_list = res
        if len(res) == 0:
            logging.fatal("The DB doesn't have any entries for the website checks. Please re-run using the file option.")


    async def _db_init(self) -> None:
        """Makes required DB initializations.

        Creates tables for saving results of health checks."""
        await self.dbc.execute_create_table(self.tablename_website, Website)
        await self.dbc.execute_create_table(self.tablename_healthcheck, Healthcheck)


    async def _db_insert_website_entry(self, website: Website) -> None:
        """Insert website healthcheck rule in the DB.

        :param website: website to insert as new row
        """
        await self.dbc.execute_insert_into_table(self.tablename_website, website)


    async def _db_insert_healthcheck_entry(self, check: Healthcheck) -> None:
        """Insert result of a website health check in the DB.
        """
        await self.dbc.execute_insert_into_table(self.tablename_healthcheck, check)


    async def _monitor(self) -> None:
        """Creates and starts a coroutine for each website that needs to be monitored.
        """
        async with ClientSession() as session:
            tasks = []
            for website in self.site_list:
                tasks.append(self._healthcheck_website(session, website))
            await asyncio.gather(*tasks)


    async def _healthcheck_website(self, session: ClientSession, website: Website):
        """Continuously performs health check on website.

        Makes an HTTP request against website according to defined time interval.
        Also does a regex check against the html reply.
        Saves result in the DB.
        """
        decimal_places = 3
        num_checks = self.num_checks
        while num_checks != 0:
            num_checks -= 1
            resp = None
            status_code = -1
            error_message = ''
            request_timestamp = time.time()

            # make request
            try:
                resp = await session.request(method="GET", url=website.url_uq)
                status_code = resp.status
            except Exception as exp:
                status_code = 598 # (Informal convention) Network read timeout error
                error_message += str(exp)
            response_time = time.time() - request_timestamp
            # check regex
            if website.regex:
                try:
                    html = await resp.text()
                    status_code = resp.status
                except Exception as exp:
                    status_code = 598 # (Informal convention) Network read timeout error
                    error_message += str(exp)
                try:
                    pattern = re.compile(website.regex)
                    if pattern.search(html):
                        match_status = RegexMatchStatus.OK
                    else:
                        match_status = RegexMatchStatus.FAIL
                except Exception as exp:
                    error_message += str(exp)
            else:
                match_status = RegexMatchStatus.NA
                response_time = time.time() - request_timestamp

            msg = f'Got HTTP response code [{status_code}] for URL: {website.url_uq}'
            if status_code >= 300:
                logger.error(msg)
            else:
                logger.info(msg)

            error_message = error_message[:250] # trim error message (defensive)
            check = Healthcheck(
                    check_id=-1,
                    website_fk=website.website_id,
                    request_timestamp=round(request_timestamp, decimal_places),
                    response_time=round(response_time, decimal_places),
                    http_status_code=status_code,
                    regex_match_status=match_status,
                    error_message=error_message)
            await self._db_insert_healthcheck_entry(check)
            await asyncio.sleep(website.interval)

