# About
CLI app to periodically perform health checks on multiple websites.

Each health check can be defined with: url, time interval, optional regex to check the response html

The list of websites can be provided as a file or in a DB via a config file. The listings in the `data` folder were created using available lists for top websites, a random time interval between 5 and 300 seconds, and for some a random text pattern to check against the response html. To test with a greater number of websites check the [corresponding section](#top-websites-list-generation) for details. This app was tested with listings up to 5000 websites.

The app stores healthcheck status results in the DB.

The motivator for this project was to work with Python async and PostgreSQL.


# TOC
<!--ts-->
- [About](#about)
- [TOC](#toc)
- [How To](#how-to)
    - [Dependencies](#dependencies)
    - [Run it](#run-it)
- [Input files data formats](#input-files-data-formats)
    - [DB config format with secrets](#db-config-format-with-secrets)
    - [websites CSV](#websites-csv)
- [Design Considerations](#design-considerations)
    - [Decisions](#decisions)
    - [Assumptions](#assumptions)
- [Bugs & Limitations & Caveats](#bugs--limitations--caveats)
- [Development tips](#development-tips)
    - [tests](#tests)
    - [pgsql inspection](#pgsql-inspection)
    - [top websites list generation](#top-websites-list-generation)
- [Lessons Learned](#lessons-learned)
- [TODO / Future Work](#todo--future-work)
    - [leverage multiprocessing](#leverage-multiprocessing)
    - [configure connection numbers](#configure-connection-numbers)
    - [consider queues](#consider-queues)
    - [Docker compose](#docker-compose)
    - [web interface for results](#web-interface-for-results)
    - [CI pipeline in Github](#ci-pipeline-in-github)
    - [improve code quality](#improve-code-quality)
- [References](#references)
<!--te-->

# How To

## Dependencies
```bash
sudo apt-get install libpq-dev postgresql-common

make venv
make deps
# and optionally:
make depsdev
```

If you do not have a DB running with an appropriate configuration file in `secrets/` yet, then the following will pull a PostgreSQL docker image, spin up a container, and save the config to `secrets/db_postgresql_container.json`
```bash
make depsdevdb
make depsdevdbrun
```

## Run it
```bash
# help menus
make help
make run -- -h
# the above make command is equivalent to doing:
source venv/bin/activate
./src/webmoncli.py -h
deactivate


config_file="secrets/db_postgresql_container.json"
make run -- --db-config "$config_file" --drop-tables
make run -- --db-config "$config_file" --sites-csv data/websites_top101_www.csv --number-healthchecks -1
```



# Input files data formats

## DB config format with secrets
```json
{
    "db_type": "postgresql",
    "db_user": "dba",
    "db_pass": "123456",
    "db_name": "defaultdb",
    "db_host": "db.example.com",
    "db_port": "5432",
    "db_ssl":  "require"
}
```
db_ssl is detailed in https://magicstack.github.io/asyncpg/current/api/index.html#connection

## websites CSV
Uses `,` as the delimiter between fields and optional `"` quotes to surrond strings.
The optional regex must not break the CSV format otherwise it will not be parsed properly.

Example:
```
www.facebook.com,10
www.twitter.com,14,foo
www.google.com,8,"feeling lucky"
```



# Design Considerations

## Decisions
- It creates two tables in the DB: `website` and `healthcheck`.
- By using `aiohttp` we can make HTTP requests in an asynchronous manner. It is also more efficient since it allows reusing connections instead of opening and closing a new one at each request. One `ClientSession` is used for each website target. Attempting to reuse the connection pool between websites led to a cascading failure.
- By using `asyncpg` for PostgreSQL we can use asyncio for database operations. According to the authors `asyncpg` is on average, 5x faster than psycopg3. https://github.com/MagicStack/asyncpg The connection pool is also configurable, although there was no need to do so.
- For sites that fail DNS resolution the healthcheck logs are marked with http status code 530, see https://en.wikipedia.org/wiki/List_of_HTTP_status_codes


## Assumptions
The initial assumptions were as follow:
- The DB isn't a bottleneck since it can handle dozens of thousands of inserts per second. https://dba.stackexchange.com/questions/48220/what-database-and-setup-can-handle-several-million-inserts-per-minute
- The OS running this script can handle thousands of connections https://en.wikipedia.org/wiki/C10k_problem
These assumptions proved out to be true during tests up to 5000 connections. Connections beyond that number haven't been tested yet.



# Bugs & Limitations & Caveats
- The biggest issue is the single process architecture. With a big enough number of websites the CPU becomes the bottleneck. For more on this see the #TODO section. This can be mitigated by adjusting the `asyncio.Semaphore()` call at the cost of delayed healthcheck (ie it won't do a healthcheck in accordance to the specified interval).
- The top website lists I got are somewhat outdated. For example some of the websites no longer exist.
- When using the local docker container for the DB, currently connections are not encrypted. Acceptable since this is for test purposes. But maybe if changing things for a docker compose file I might as well setup certificates and enable this.
- Some websites refuse to cooperate with the http GET request, the reason still unknown. For those sites that end up triggering an exception they are tagged with status code 555. On one occasion, now fixed, was sending incompatible request headers (accept encoding had `br` but the app was missing the brotli library).
- ~~Redirect doesn't work. When making a `ClientSession.request` despite `allow_redirects` defaulting to True, if you try to access an incorrect domain, eg a naked domain, if it fails then it won't automatically try the `www.` subdomain. Browsers do a bit of magic in this regard. But another example of this can be seen with `ec.europa.eu` which on the browser redirects to `commission.europa.eu` and in curl it gets a redirect status code, but it didn't work in this tool with `ClientSession.request`.~~ TBC maybe an aiohttp issue which was present in 3.9.5 but fixed with 3.11.13?




# Development tips

## tests
This projects has the following tests:
- unit tests: test a module, not making any IO calls, potentially mocking some components
- integration tests: tests one or more modules, where IO calls are calls (eg: to the database)
- smoke tests: end to end test, test the full app lifecycle

## pgsql inspection
```bash
export $(jq -r 'to_entries|map("\(.key)=\(.value)")|.[]' secrets/db_postgresql_container.json)
psql --host "$db_host" --port "$db_port" --username "$db_user" --password --dbname "$db_name"
```

```sql
SELECT * FROM healthcheck ORDER BY check_id DESC LIMIT 20;
SELECT * FROM website ORDER BY website_id DESC LIMIT 10;

SELECT COUNT(*) FROM website;
SELECT COUNT(*) FROM healthcheck;

SELECT COUNT(*) FROM healthcheck WHERE http_status_code = 598;
SELECT COUNT(*) FROM healthcheck WHERE http_status_code = 555;

SELECT h.* FROM healthcheck h JOIN website w ON h.website_fk = w.website_id WHERE h.http_status_code = 555 AND w.url_uq = 'https://sciencedirect.com:443';
SELECT h.* FROM healthcheck h JOIN website w ON h.website_fk = w.website_id WHERE w.url_uq = 'https://sciencedirect.com:443';

-- show all unsuccessful requests for each site
SELECT w.url_uq, h.http_status_code, h.error_message FROM website w JOIN healthcheck h ON h.website_fk = w.website_id WHERE h.http_status_code != 200;
-- show all distinct unsuccessful requests for each site
SELECT DISTINCT w.url_uq, h.http_status_code, h.error_message FROM website w JOIN healthcheck h ON h.website_fk = w.website_id WHERE h.http_status_code != 200;
-- show a count for each distinct unsuccessful request per site
SELECT w.url_uq, h.http_status_code AS http_code, h.error_message, COUNT(*) AS x_count
FROM website w
JOIN healthcheck h ON h.website_fk = w.website_id
WHERE h.http_status_code != 200
GROUP BY w.url_uq, h.http_status_code, h.error_message
ORDER BY x_count DESC;
```

## top websites list generation
sources for the list of top websites:
https://gist.githubusercontent.com/bejaneps/ba8d8eed85b0c289a05c750b3d825f61/raw/6827168570520ded27c102730e442f35fb4b6a6d/websites.csv
https://gist.github.com/chilts/7229605
    https://downloads.majesticseo.com/majestic_million.csv

```bash
# top 100 websites
wget 'https://gist.githubusercontent.com/bejaneps/ba8d8eed85b0c289a05c750b3d825f61/raw/6827168570520ded27c102730e442f35fb4b6a6d/websites.csv'
cat websites.csv | head -n 100 | cut -f2 -d',' | while read line; do echo "$line,$(($RANDOM % 295 + 5))"; done > websites_100.csv
# NOTE: for majestic_million.csv use `cut -f3 ...`

# top 100 websites with random text pattern to search for
websites="websites_100" ; words='/usr/share/dict/american-english' ; cat "$websites.csv" | while read line; do if (( $RANDOM % 5 == 0 )); then word1=$(shuf -n 1 $words);  word2=$(shuf -n 1 $words); echo "$line,\"$word1 $word2\""; else echo "$line"; fi; done > "${websites}_regex.csv"

# add www subdomain
awk 'BEGIN{FS=OFS=","} {gsub(/"/, "", $1); if ($1 ~ /^[^.]*\.[^.]*$/) {sub(/^/, "www.");} print}' websites_top101.csv > websites_top101_www.csv 
```



# Lessons Learned
- Only run `asyncio.run()` once and only once! Even if it looks like you can separate the business logic. Chances are you'll lose your async loop context and it will break things
    - IIRC I got this error: `RuntimeError: no running event loop sys:1: RuntimeWarning: coroutine 'worker' was never awaited`
- You need a DB connection pool, because coroutines can't share the connection
    - IIRC I got this error: `asyncpg  cannot perform operation: another operation is in progress`
    - https://stackoverflow.com/questions/66444620/asyncpg-cannot-perform-operation-another-operation-is-in-progress/66448094#66448094
    - https://github.com/MagicStack/asyncpg/issues/258
- You need to close the DB connection pool, otherwise you'll always get an exception at the end.
- Despite what some information may say, you shouldn't share a `ClientSession` connection pool with other websites. Because if you do you'll end up getting a cascading `asyncio.TimeoutError`. It's as if that connection got broken beyond repair. If one `session.request` failed (eg: timeout exceeded) then it would break all other requests to other sites. I tried using `TCPConnector(limit=none, enable_cleanup_closed=True, force_close=True)` but that didn't solve it. The only working solution to fix the cascading `asyncio.TimeoutError` was to create a ClientSession per site and also to using `asyncio.Semaphore`.
- http status code 400 can be caused by incorrect request headers. The way to fix it was to use a browser web tools and see what it is sending exactly.
- Connection throttling is the crux of the matter. With a single process architecture and using `asyncio.Semaphore(1)` then the average number of RPS will be very low, around 3, which will result in healthchecks not being made on time. OTOT using `asyncio.Semaphore(total_number_websites)` will initially get us a very large number of RPS but will eventually hit a CPU ceiling and will then trigger a cascade of `asyncio.TimeoutError` exceptions. So there is magic to this number. Using a value of 100 was almost enough to handle 5000 websites: there were no cascading failures, the actual time of execution duration was close to the expected (ie num_checks*max_interval) but still longer, and there were some cases of registered timeouts. Monitor resouce usage (htop) and inspecting the DB for errors and latency is important. A value of 150 resulted in more failures.



# TODO / Future Work

## leverage multiprocessing
It was observed that with a big enough number of websites, and no use of or lax use of semaphore, the CPU becomes the bottleneck which will then trigger a series of cascading `asyncio.TimeoutError` exceptions for all websites and future healthchecks. These failures can be mitigated with `asyncio.Semaphore()` at the potential expense of delayed healthchecks (ie the defined healthcheck interval isn't respected).
The async coroutines run inside a single process and because of the GIL using threads won't fix this issue.
A solution, which at the very least will always improve scalability, can be to split the list of websites to monitor by a number equal to, give or take, the number of CPU cores available in the system.

## configure connection numbers
- Configure pool sizes for DB requests. So far there was no need to do so.
- Configure request numbers for GET requests. Currently we are using `asyncio.Semaphore` with a "magical" number (ie static and possibly machine dependent). A better approach would be for this to be set dynamically, possibly based on the ratio between the number of websites by the average healthcheck interval time. Other considerations could be: response times, CPU and net load. Note that this doesn't invalidate the points mentioned on multiprocessing issue (ie these are independent and having multiprocessing would allow for better performance and scalability).


## consider queues
Consider if using an async queue for the regex check work would be beneficial.

## Docker compose
Maybe create a docker compose file with one container for the web server and another for the db server. Also update makefile to reflect this
Worth noting that the docker commands to spin a test DB are still useful on their own for dev purposes.

## web interface for results
Create a website to display the results. Maybe using FastAPI.
In the context of Docker compose this would be another container.


## CI pipeline in Github

## improve code quality
Integrate the use of code quality tools, with some of them potentially in the form of git pre-commit hooks.
- [X] isort: auto format imports
- [X] black or yapf: code auto formating
- [X] pylint: check for potential errors and enforcing coding standards; other alternatives are flake8 or ruff
- [X] mypy: static type checker
- [ ] bandit: security linter
- [ ] coverage: measures code coverage by tests


# References
- regex expression adapted from https://stackoverflow.com/questions/9530950/parsing-hostname-and-port-from-string-or-url/9531189#9531189
- async info and logic from https://realpython.com/async-io-python
- asyncpg connection pool issue https://stackoverflow.com/questions/66444620/asyncpg-cannot-perform-operation-another-operation-is-in-progress
- retry logic losely based on https://gist.github.com/alairock/a0235eae85c62f0f0f7b81bec8aa378a

