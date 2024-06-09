import asyncio
from aiohttp import ClientSession
import csv
import json
import re
import logging
from types import SimpleNamespace
from .database_connector import DatabaseConnector
from .website import Website
import ipdb

logger = logging.getLogger("webmonitor")

class WebMonitor:
    """Monitors health status of websites and saves results to a DB.
    """

    def __init__(self, db_config: str, site_list: str):
        self.db_config = db_config
        self.site_list = site_list
        self.conn = None


    def run(self):
        asyncio.run(self._initialize())
        asyncio.run(self._monitor())


    async def _initialize(self) -> None:
        # read DB config
        self._read_config()
        # init DB connection
        cfg = SimpleNamespace(**{k: v for k, v in self.db_config.items()})
        self.conn = DatabaseConnector(cfg.db_type, cfg.db_user, cfg.db_pass, cfg.db_name, cfg.db_host, cfg.db_port, cfg.db_ssl)
        await self._db_init()
        # read site list either from file or DB
        if self.site_list.endswith('.csv'):
            self._read_sites()
        elif self.site_list.endswith('.json'):
            await self._read_sites_from_db()
        else:
            raise NotImplementedError


    def _read_config(self) -> None:
        with open(self.db_config, 'r') as file:
            self.db_config = json.load(file)


    def _read_sites(self) -> None:
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
                sites.append(Website(url=url, interval=interval, regex=regex))
        self.site_list = sites


    @staticmethod
    def get_valid_url(url: str):
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
        # TODO: read sites from DB
        pass


    async def _db_init(self) -> None:
        # TODO: create tables to save results if they dont exist
        pass


    async def _db_insert_healthcheck_result(self) -> None:
        # TODO: insert healthcheck result in DB
        pass


    async def _monitor(self) -> None:
        async with ClientSession() as session:
            tasks = []
            for website in self.site_list:
                tasks.append(self._healthcheck_website(session, website))
            await asyncio.gather(*tasks)


    async def _healthcheck_website(self, session: ClientSession, website: Website):
        while True:
            resp = await session.request(method="GET", url=website.url)
            resp.raise_for_status()
            logger.info("Got response [%s] for URL: %s", resp.status, website.url)
            html = await resp.text()
            await asyncio.sleep(website.interval)



