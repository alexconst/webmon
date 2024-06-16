import asyncio
import csv
import json
import logging
import os
import re
import sys
import time
from types import SimpleNamespace
from typing import List, Optional

from aiohttp import ClientSession, ClientTimeout, TCPConnector

from .database_connector_factory import DatabaseConnectorFactory, DatabaseType
from .healthcheck import Healthcheck, RegexMatchStatus
from .website import Website

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
        self.db_config = db_config    # after proper init it will be a map with the DB config
        self.site_list = site_list    # after proper init it will be a list of website healthcheck rules
        self.tablename_website = 'website'
        self.tablename_healthcheck = 'healthcheck'
        self.num_checks = num_checks
        self.dbc = None    # DB connector

    async def run(self, action: str) -> None:
        """Main entry point. Performs selected action.

        :param action: supported values: monitor, drop-tables.
            If 'monitor' then it performs required initialization and then monitors websites health.
            If 'drop-tables' it drops the tables used for websites and healthchecks.
        """
        if action in ['monitor', 'drop-tables']:
            with open(self.db_config, 'r') as file:
                self.db_config = json.load(file)
            db_type = DatabaseType[self.db_config['db_type'].upper()] # type: ignore
            self.dbc = await DatabaseConnectorFactory(db_type, self.db_config).get_connector() # type: ignore
            await self.dbc.open() # type: ignore
        if action == 'monitor':
            await self._prepare()
            await self._monitor()
        elif action == 'drop-tables':
            await self._drop_tables()
        else:
            logging.fatal(f'Invalid action: ${action}')
        await self._finish()

    async def _finish(self) -> None:
        if self.dbc:
            await self.dbc.close() # type: ignore

    async def _drop_tables(self) -> None:
        await self.dbc.execute_drop_table(self.tablename_healthcheck) # type: ignore
        await self.dbc.execute_drop_table(self.tablename_website) # type: ignore

    async def _prepare(self) -> None:
        """Create DB tables. Process list of websites to healthcheck. Configure system resources limit.
        """
        await self.dbc.execute_create_table(self.tablename_website, Website) # type: ignore
        await self.dbc.execute_create_table(self.tablename_healthcheck, Healthcheck) # type: ignore
        # if a website list was provided then read it and setup the DB
        if self.site_list:
            if self.site_list.endswith('.csv') and os.path.exists(self.site_list):
                self._read_sites_from_file()
                await self.dbc.execute_create_table(self.tablename_website, Website) # type: ignore
                await self._db_insert_many_website_entry(self.site_list) # type: ignore
            else:
                logger.fatal(f"Invalid file provided. Either file doesn't exist or it doesn't have a .csv extension: {self.site_list}")
                await self._finish()
                sys.exit(1)
        # always read website list from the DB (either due to user option, or just to have website_id info as per the DB)
        await self._read_sites_from_db()
        # increase system resource limits
        WebMonitor.config_system_resource_limits(len(self.site_list), logger)

    def _read_sites_from_file(self) -> None:
        """Read list of websites to perform health checks from a CSV file.
        """
        delimiter = ','
        split_row = lambda row: (row[0], row[1], row[2]) if len(row) == 3 else (row[0], row[1], '')
        sites = []
        with open(self.site_list, 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=delimiter)
            for idx, row in enumerate(csv_reader):
                if not row:    # skip blank lines
                    continue
                if idx == 0 and f'host{delimiter}interval' in str(row):
                    continue
                url, interval, regex = split_row(row)
                url = WebMonitor.get_valid_url(url, False)    # better disable any "magic" for non-naked domain
                sites.append(Website(website_id=-1, url_uq=url, interval=interval, regex=regex))
        self.site_list = sites # type: ignore

    @staticmethod
    def get_valid_url(url: str, no_naked_domain: bool = False) -> str:
        """Receives a malformed url and returns a well formed one.

        :param url: input url
        :param no_naked_domain: if true then it will append `www.` to any input naked domain
        :return: a well formed URL
        :rtype: string
        """
        url_regex = '(?P<protocol>http.*://)?(?P<host>[^:/ ]+).?(?P<port>[0-9]*)/?(?P<path>.*)'
        m = re.search(url_regex, url)
        protocol = m.group('protocol') # type: ignore
        host = m.group('host') # type: ignore
        port = m.group('port') # type: ignore
        path = m.group('path') # type: ignore
        if no_naked_domain and host.count('.') < 2:
            host = f'www.{host}'
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
        res = await self.dbc.fetch_all_from_table(self.tablename_website, Website) # type: ignore
        self.site_list = res
        if len(res) == 0:
            logger.fatal("The DB doesn't have any entries for the website checks. Please re-run using the file option.")
            await self._finish()
            sys.exit(1)

    @staticmethod
    def config_system_resource_limits(hint: int, logger: Optional[logging.Logger] = None) -> None:
        import resource
        factor = 2
        soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
        new_soft_limit = max(soft_limit + hint * factor, resource.RLIM_INFINITY)
        # increase max number of FDs soft limit to based on the number of websites, and maintain the hard limit because only root can increase it
        resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft_limit, hard_limit))
        new_soft_limit, new_hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
        if logger:
            logger.info(f"OS's soft limit on max number of file descriptors: old value was {soft_limit}, new value is {new_soft_limit}.")

    async def _db_insert_many_website_entry(self, websites: List[Website]) -> None:
        """Insert multiple website healthcheck rules in the DB.

        :param websites: list of websites to insert in the table
        """
        await self.dbc.execute_insert_many_into_table(self.tablename_website, websites) # type: ignore

    async def _db_insert_healthcheck_entry(self, check: Healthcheck) -> None:
        """Insert result of a website health check in the DB.
        """
        await self.dbc.execute_insert_many_into_table(self.tablename_healthcheck, [check]) # type: ignore

    async def _monitor(self) -> None:
        """Creates and starts a coroutine for each website that needs to be monitored.
        """
        sem = asyncio.Semaphore(100)
        tasks = []
        for website in self.site_list:
            tasks.append(self._healthcheck_website(website, sem)) # type: ignore
        await asyncio.gather(*tasks)

    async def _healthcheck_website(self, website: Website, sem: asyncio.Semaphore) -> None:
        """Continuously performs healthchecks on website. Makes http request and saves result in the DB.

        :param website: website info
        :param sem: semaphore to control number of simultaneous connections
        """
        request_headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'Connection': 'keep-alive'
        }
        timeout_seconds = 15
        num_checks = self.num_checks
        regex_pattern = None
        if website.regex:
            regex_pattern = re.compile(website.regex)
        connector = TCPConnector(limit=None, enable_cleanup_closed=True, force_close=True)   # type: ignore  # limit=None for no limit 
        total_timeout = ClientTimeout(total=timeout_seconds)
        async with ClientSession(connector=connector, timeout=total_timeout) as session:
            while num_checks != 0:
                num_checks -= 1
                await asyncio.sleep(website.interval)
                check = await self._request_website(session, website, sem, request_headers, regex_pattern) # type: ignore

                msg = f'Got HTTP response code [{check.http_status_code}] for URL: {website.url_uq}'
                if check.http_status_code >= 300:
                    logger.error(msg)
                else:
                    logger.info(msg)
                if check.error_message:
                    check.error_message = f"{website.url_uq} {check.error_message}"
                    check.error_message = check.error_message[:300]    # trim error message to something reasonable

                await self._db_insert_healthcheck_entry(check)
                logger.debug(f'Finished inserting in DB the check results for: {website.url_uq}')

    async def _request_website(self, session: ClientSession, website: Website, sem: asyncio.Semaphore, headers: dict,
                               regex_pattern: re.Pattern) -> "Healthcheck":
        """Makes HTTP request.

        Makes an HTTP request against website according to defined time interval.
        Also does a regex check against the html reply.

        :param session: http client session
        :param website: website info
        :param sem: semaphore to control number of simultaneous connections
        :param headers: http request headers
        :param regex_pattern: regex pattern to check html for
        :return: healthcheck results
        :rtype: Healthcheck
        """
        decimal_places = 3
        resp = None
        status_code = -1
        error_message = ''
        logger.debug(f'Will make a web request for: {website.url_uq}')
        request_timestamp = time.time()
        html = ''

        # make request
        try:
            logger.debug(f'Waiting for semaphore unlock to make web request for: {website.url_uq}')
            async with sem:
                logger.debug(f'Semaphore unlocked for making web request for: {website.url_uq}')
                resp = await session.request(method="GET", headers=headers, url=website.url_uq)
                logger.debug(f'OKed making web request for: {website.url_uq}')
                if website.regex:
                    html = await resp.text()
                resp.close()    # https://github.com/aio-libs/aiohttp/issues/5277#issuecomment-944448361
            status_code = resp.status
        except asyncio.TimeoutError as exp:
            logger.debug(f'FAILed making web request for: {website.url_uq}')
            status_code = 598    # (Informal convention) Network read timeout error
            error_message += f"{str(exp.__class__)} {str(exp)}"
        except Exception as exp:
            status_code = 555    # observed expections include: ClientConnectorError, ClientOSError
            error_message += f"{str(exp.__class__)} {str(exp)}"
        response_time = time.time() - request_timestamp

        # check regex
        if resp and website.regex:
            if html and regex_pattern.search(html):
                match_status = RegexMatchStatus.OK
            else:
                match_status = RegexMatchStatus.FAIL
        else:
            match_status = RegexMatchStatus.NA

        check = Healthcheck(check_id=-1,
                            website_fk=website.website_id,
                            request_timestamp=round(request_timestamp, decimal_places),
                            response_time=round(response_time, decimal_places),
                            http_status_code=status_code,
                            regex_match_status=match_status,
                            error_message=error_message)
        return check
