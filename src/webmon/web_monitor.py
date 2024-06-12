import asyncio
from aiohttp import ClientSession
import csv
import json
import re
import logging
from types import SimpleNamespace
import time
from .database_connector_factory import DatabaseConnectorFactory, DatabaseType
from .website import Website
from .healthcheck import Healthcheck, RegexMatchStatus
import ipdb

logger = logging.getLogger("webmonitor")

class WebMonitor:
    """Monitors health status of websites and saves results to a DB.
    """

    def __init__(self, db_config: str, site_list: str, num_checks: int):
        """Constructor.

        :param db_config: filename with DB config
        :param site_list: filename with list of websites to check
        :param num_checks: how many checks to perform per website before finishing. Use -1 for infinite.
        """
        self.db_config = db_config
        self.site_list = site_list
        self.tablename_website = 'website'
        self.tablename_healthcheck = 'healthcheck'
        self.num_checks = num_checks


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


    async def _drop_tables(self):
        #self._read_config()
        #cfg = SimpleNamespace(**{k: v for k, v in self.db_config.items()})
        # DatabaseType[cfg.db_type.upper()]
        #self.conn = DatabaseConnectorFactory(cfg.db_type, cfg.db_user, cfg.db_pass, cfg.db_name, cfg.db_host, cfg.db_port, cfg.db_ssl)
        #await self.conn.connect()
        #await self.conn.drop_table(self.tablename_healthcheck)
        #await self.conn.drop_table(self.tablename_website)
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
        # get db connector
        db_type = DatabaseType[self.db_config['db_type'].upper()]
        self.dbc = await DatabaseConnectorFactory(db_type, self.db_config).get_connector()
        # init DB connection
        #cfg = SimpleNamespace(**{k: v for k, v in self.db_config.items()})
        #self.conn = DatabaseConnectorFactory(cfg.db_type, cfg.db_user, cfg.db_pass, cfg.db_name, cfg.db_host, cfg.db_port, cfg.db_ssl)
        #await self.conn.connect()
        await self._db_init()
        # read site list either from file or DB
        if self.site_list.endswith('.csv'):
            self._read_sites_from_file()
            # but if it's from CSV then we also need to save it in the DB
            #await self.conn.create_table(self.tablename_website, Website)
            await self.dbc.execute_create_table(self.tablename_website, Website)
        elif self.site_list.endswith('.json'):
            await self._read_sites_from_db()
        else:
            raise NotImplementedError


    def _read_config(self) -> None:
        """Read DB config.
        """
        with open(self.db_config, 'r') as file:
            self.db_config = json.load(file)


    def _read_sites_from_file(self) -> None:
        """Read list of websites to perform health checks from a CSV file.
        """
        delimiter = ','
        #split_host_port = lambda url: (url.split(':')[0], url.split(':')[1]) if ':' in url else (url, '443')
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
                #host, port = split_host_port(url)
                url = WebMonitor.get_valid_url(url)
                sites.append(Website(website_id=-1, url=url, interval=interval, regex=regex))
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
        # TODO: read sites from DB
        #with open(self.db_config, 'r') as file:
        #    self.db_config = json.load(file)
        #cfg = SimpleNamespace(**{k: v for k, v in self.db_config.items()})
        #self.site_list
        pass

    async def _db_init(self) -> None:
        """Makes required DB initializations.

        Creates tables for saving results of health checks."""
        #await self.conn.create_table(self.tablename_healthcheck, Healthcheck)
        await self.dbc.execute_create_table(self.tablename_website, Website)
        await self.dbc.execute_create_table(self.tablename_healthcheck, Healthcheck)


    async def _db_insert_healthcheck_result(self, check: Healthcheck) -> None:
        """Insert result of a website health check in the DB.
        """
        #await self.conn.create_table(self.tablename_healthcheck, check)
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
                resp = await session.request(method="GET", url=website.url)
                status_code = resp.status
            except asyncio.exceptions as exp:
                status_code = 598 # (Informal convention) Network read timeout error
                error_message += str(exp)
            response_time = time.time() - request_timestamp
            logger.info("Got response [%s] for URL: %s", resp.status, website.url)
            # check regex
            if website.regex:
                try:
                    html = await resp.text()
                    status_code = resp.status
                except asyncio.exceptions as exp:
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
            check = Healthcheck(
                    check_id=-1,
                    website_fk=website.website_id,
                    request_timestamp=round(request_timestamp, decimal_places),
                    response_time=round(response_time, decimal_places),
                    http_status_code=status_code,
                    regex_match_status=match_status,
                    error_message=error_message)
            await self._db_insert_healthcheck_result(check)
            await asyncio.sleep(website.interval)

