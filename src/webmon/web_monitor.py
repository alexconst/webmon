import asyncio
from aiohttp import ClientSession
import csv
import json
import re
import logging
from types import SimpleNamespace
import time
from .database_connector import DatabaseConnector
from .website import Website
from .healthcheck import Healthcheck, RegexMatchStatus
import ipdb

logger = logging.getLogger("webmonitor")

class WebMonitor:
    """Monitors health status of websites and saves results to a DB.
    """

    def __init__(self, db_config: str, site_list: str):
        """Constructor. Lazy initialization.
        """
        self.db_config = db_config
        self.site_list = site_list
        self.conn = None
        self.tablename_website = 'website'
        self.tablename_healthcheck = 'healthcheck'


    def run(self):
        """Performs initialization and continues doing website health check status.
        """
        asyncio.run(self._initialize())
        asyncio.run(self._monitor())


    def drop_tables(self):
        """Drop tables used by app.
        """
        asyncio.run(self._drop_tables())


    async def _drop_tables(self):
        self._read_config()
        cfg = SimpleNamespace(**{k: v for k, v in self.db_config.items()})
        self.conn = DatabaseConnector(cfg.db_type, cfg.db_user, cfg.db_pass, cfg.db_name, cfg.db_host, cfg.db_port, cfg.db_ssl)
        await self.conn.connect()
        await self.conn.drop_table(self.tablename_healthcheck)
        await self.conn.drop_table(self.tablename_website)

    async def _initialize(self) -> None:
        """Read DB config. Read list of websites to check. Start connection to DB.
        """
        # read DB config
        self._read_config()
        # init DB connection
        cfg = SimpleNamespace(**{k: v for k, v in self.db_config.items()})
        self.conn = DatabaseConnector(cfg.db_type, cfg.db_user, cfg.db_pass, cfg.db_name, cfg.db_host, cfg.db_port, cfg.db_ssl)
        await self.conn.connect()
        await self._db_init()
        # read site list either from file or DB
        if self.site_list.endswith('.csv'):
            self._read_sites_from_file()
            # but if it's from CSV then we also need to save it in the DB
            await self.conn.create_table(self.tablename_website, Website)
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

        Creates table for saving results of health checks."""
        await self.conn.create_table(self.tablename_healthcheck, Healthcheck)


    async def _db_insert_healthcheck_result(self, check: Healthcheck) -> None:
        """Insert result of a website health check in the DB.
        """
        await self.conn.create_table(self.tablename_healthcheck, check)


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
        ipdb.set_trace()
        while True:
            request_timestamp = time.time()
            resp = await session.request(method="GET", url=website.url)
            #resp.raise_for_status()
            logger.info("Got response [%s] for URL: %s", resp.status, website.url)
            if website.regex:
                html = await resp.text()
                response_time = time.time() - request_timestamp
                pattern = re.compile(website.regex)
                if pattern.search(html):
                    match_status = RegexMatchStatus.OK
                else:
                    match_status = RegexMatchStatus.FAIL
            else:
                match_status = RegexMatchStatus.NA
                response_time = time.time() - request_timestamp
            error_message = ''
            if resp.status != 200:
                error_message = 'TODO'
            check = Healthcheck(
                    check_id=-1,
                    request_timestamp=request_timestamp,
                    response_time=response_time,
                    http_status_code=resp.status,
                    regex_match_status=match_status,
                    error_message=error_message)
            await self._db_insert_healthcheck_result(check)
            await asyncio.sleep(website.interval)

