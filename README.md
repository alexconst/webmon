# About
CLI app to periodically perform health checks on multiple websites.
Each health check can be defined with: url, time interval, optional regex to check the response html
The list of websites can be provided as a file or in a DB via a config file.
The app stores healthcheck status results in the DB.


# How To

## Dependencies
```bash
sudo apt-get install libpq-dev postgresql-common

make venv
make deps
```

## Run it
```bash
make help
make run -- -h

source venv/bin/activate
./src/webmoncli.py --db-config secrets/db_postgresql.json --drop-tables
./src/webmoncli.py --db-config secrets/db_postgresql.json --sites-csv data/websites_top101_www.csv --number-healthchecks -1
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


## Assumptions
The initial assumptions were as follow:
- The DB isn't a bottleneck since it can handle dozens of thousands of inserts per second. https://dba.stackexchange.com/questions/48220/what-database-and-setup-can-handle-several-million-inserts-per-minute
- The OS running this script can handle thousands of connections https://en.wikipedia.org/wiki/C10k_problem
These proved out to be true during tests up to 5000 connections. Connections beyond that number haven't been tested yet.


# Development tips

## tests
This projects has the following tests:
- unit tests: test a module, not making any IO calls, potentially mocking some components
- integration tests: tests one or more modules, where IO calls are calls (eg: to the database)
- smoke tests: end to end test, test the full app lifecycle

## pgsql inspection
```bash
export $(jq -r 'to_entries|map("\(.key)=\(.value)")|.[]' secrets/db_postgresql.json)
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

SELECT w.url_uq, h.error_message FROM website w JOIN healthcheck h ON h.website_fk = w.website_id WHERE h.http_status_code != 200;

-- won't run, or at least on low end DB server
SELECT w.url_uq, (SELECT COUNT(*) FROM healthcheck WHERE website_fk = w.website_id AND http_status_code = 200) AS count_http_200, (SELECT COUNT(*) FROM healthcheck WHERE website_fk = w.website_id AND http_status_code != 200) AS count_not_http_200   FROM website w JOIN healthcheck h ON h.website_fk = w.website_id WHERE h.http_status_code != 200;
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



# Lessons learned
- Only run `asyncio.run()` once and only once! Even if it looks like you can separate the business logic. Chances are you'll lose your async loop context and it will break things
    - IIRC I got this error: `RuntimeError: no running event loop sys:1: RuntimeWarning: coroutine 'worker' was never awaited`
- You need a DB connection pool, because coroutines can't share the connection
    - IIRC I got this error: `asyncpg  cannot perform operation: another operation is in progress`
    - https://stackoverflow.com/questions/66444620/asyncpg-cannot-perform-operation-another-operation-is-in-progress/66448094#66448094
    - https://github.com/MagicStack/asyncpg/issues/258
- You need to close the DB connection pool, otherwise you'll always get an exception at the end.
- Despite what some information may say, you shouldn't share a `ClientSession` connection pool with other websites. Because if you do you'll end up getting a cascading `asyncio.TimeoutError`. It's as if that connection got broken beyond repair. If one `session.request` failed (eg: timeout exceeded) then it would break all other requests to other sites. I tried using `TCPConnector(limit=none, enable_cleanup_closed=True, force_close=True)` but that didn't solve it. The only working solution to fix the cascading `asyncio.TimeoutError` was to create a ClientSession per site and also to using `asyncio.Semaphore`.





# Bugs & Caveats
- Redirect doesn't work. When making a `ClientSession.request` despite `allow_redirects` defaulting to True, if you try to access an incorrect domain, eg a naked domain, if it fails then it won't automatically try the `www.` subdomain. Browsers do a bit of magic in this regard. But another example of this can be seen with `ec.europa.eu` which on the browser redirects to `commission.europa.eu` and in curl it gets a redirect status code, but it didn't work in this tool with `ClientSession.request`.



# TODO / Future Work

## configure pool sizes
Configure pool sizes for web requests and DB requests.
So far there was no need to do so, but OTOH the codebase does currently use `asyncio.Semaphore`.

## consider queues
Consider if using an async queue for the regex check work would be beneficial.

## replace venv with Docker
Also update makefile to reflect this

## CI pipeline in Github

## improve code quality
Integrate the use of code quality tools, with some of them potentially in the form of git pre-commit hooks.
- black: code auto formating
- isort: auto format imports
- pylint: check for potential errors and enforcing coding standards; other alternatives are flake8 or ruff
- mypy: static type checker
- bandit: security linter
- coverage: measures code coverage by tests


# References
- regex expression adapted from https://stackoverflow.com/questions/9530950/parsing-hostname-and-port-from-string-or-url/9531189#9531189
- async info and logic from https://realpython.com/async-io-python
- asyncpg connection pool issue https://stackoverflow.com/questions/66444620/asyncpg-cannot-perform-operation-another-operation-is-in-progress
- retry logic losely based on https://gist.github.com/alairock/a0235eae85c62f0f0f7b81bec8aa378a

