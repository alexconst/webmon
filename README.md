# About
CLI app to periodically perform health checks on multiple websites.
Each health check can be defined with: url, time interval, optional regex to check the response html
The list of websites can be provided as a file or in a DB via a config file.
The app stores status results in the DB.


# How To

## Dependencies
```bash
sudo apt-get install libpq-dev postgresql-common

make venv
make deps

make run -- -h
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
Uses `,` as the delimiter between fields.
Currently there is no escaping of this character, so if the regex includes it then it will break parsing.
Example:
```
facebook.com,10
twitter.com,14
google.com,8,feeling lucky
```



# Design

## Considerations
- It creates two tables in the DB: `website` and `healthcheck`.
- By using `aiohttp` we can make HTTP requests in an asynchronous manner. It is also more efficient since it allows reusing connections instead of opening and closing a new one at each request. The size of the connection pool is also configurable. https://docs.aiohttp.org/en/stable/http_request_lifecycle.html
- By using `asyncpg` for PostgreSQL we can do use asyncio for database operations. According to the authors `asyncpg` is on average, 5x faster than psycopg3. https://github.com/MagicStack/asyncpg The connection pool is configurable.


## Assumptions
- The DB isn't a bottleneck since it can handle dozens of thousands of inserts per second. https://dba.stackexchange.com/questions/48220/what-database-and-setup-can-handle-several-million-inserts-per-minute
- The OS running this script can handle thousands of connections https://en.wikipedia.org/wiki/C10k_problem



# Development tips

## pgsql inspect
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

## generate list of top websites
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



# Bugs & Caveats
- Redirect don't work. When making a `ClientSession.request` despite `allow_redirects` defaulting to True, if you try to access an incorrect domain, eg a naked domain, if it fails then it won't automatically try the `www.` subdomain. Browsers do a bit of magic in this regard. Another example is with `ec.europa.eu` which on the browser redirects to `commission.europa.eu` and in curl it gets a redirect status code, but in this tool it fails.


# References
- regex expression adapted from https://stackoverflow.com/questions/9530950/parsing-hostname-and-port-from-string-or-url/9531189#9531189
- async info and logic from https://realpython.com/async-io-python
- asyncpg connection pool issue https://stackoverflow.com/questions/66444620/asyncpg-cannot-perform-operation-another-operation-is-in-progress
- retry logic forked from https://gist.github.com/alairock/a0235eae85c62f0f0f7b81bec8aa378a



# TODO / Future Work

## system ulimits
```bash
ulimit -a
ulimit -Ha
```
By default the soft limit for FD is 1024 :(
Should be able to override that with `ulimit -n $number`

This setting may also be relevant: `/proc/sys/net/core/somaxconn`

```python
import resource

# Set the soft limit to a very high value (e.g., 20000) and the hard limit to infinity
resource.setrlimit(resource.RLIMIT_NOFILE, (2 ** 14, resource.RLIM_INFINITY))
```

Related `/proc/sys/net/ipv4/tcp_keepalive_time`


## configure pool sizes
For web requests and DB requests.

## batched/queued inserts in DB

## replace venv with Docker
also update makefile to reflect this

## SQL injection
Given that we are in control of our own config files this isn't an immediate concern.


