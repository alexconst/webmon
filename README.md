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



# References
- regex expression adapted from https://stackoverflow.com/questions/9530950/parsing-hostname-and-port-from-string-or-url/9531189#9531189
- async info and logic from https://realpython.com/async-io-python
- asyncpg connection pool issue https://stackoverflow.com/questions/66444620/asyncpg-cannot-perform-operation-another-operation-is-in-progress
- retry logic forked from https://gist.github.com/alairock/a0235eae85c62f0f0f7b81bec8aa378a



# TODO / Future Work

## configure pool sizes
For web requests and DB requests.

## batched/queued inserts in DB

## replace venv with Docker
also update makefile to reflect this

## SQL injection
Given that we are in control of our own config files this isn't an immediate concern.


