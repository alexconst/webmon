import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../src/'))
from webmon.database_connector import DatabaseConnector
from webmon.website import Website
from webmon.healthcheck import Healthcheck, RegexMatchStatus
import ipdb


def clean(text):
    return text.replace('\n', ' ').replace('  ', ' ').strip(' ')


def test_get_query_create_table():
    website = Website(website_id=-1, url_uq='https://foo.bar', interval=5, regex='')

    res = DatabaseConnector.get_query_create_table('website', website, True)
    exp = 'CREATE TABLE IF NOT EXISTS website (\nwebsite_id SERIAL,\nurl_uq TEXT UNIQUE,\ninterval INT,\nregex TEXT,\nPRIMARY KEY (website_id)\n);'
    assert clean(res) == clean(exp)

    res = DatabaseConnector.get_query_create_table('website', website, False)
    exp = 'CREATE TABLE IF NOT EXISTS website (\nwebsite_id INT,\nurl_uq TEXT,\ninterval INT,\nregex TEXT);'
    assert clean(res) == clean(exp)

    check = Healthcheck(check_id=123, website_fk=33, request_timestamp=1718055080.050827, response_time=3.14, http_status_code=200, regex_match_status=RegexMatchStatus.OK, error_message='')
    res = DatabaseConnector.get_query_create_table('healthcheck', check, True)
    exp = 'CREATE TABLE IF NOT EXISTS healthcheck (\ncheck_id SERIAL,\nwebsite_fk INT,\nrequest_timestamp FLOAT,\nresponse_time FLOAT,\nhttp_status_code INT,\nregex_match_status INT,\nerror_message TEXT,\nPRIMARY KEY (check_id)\n);'
    assert clean(res) == clean(exp)


def test_get_query_drop_table():
    website = Website(website_id=-1, url_uq='https://foo.bar', interval=5, regex='')

    res = DatabaseConnector.get_query_drop_table('website')
    exp = 'DROP TABLE IF EXISTS website;'
    assert clean(res) == clean(exp)


def test_get_query_insert_into_table():
    website = Website(website_id=-1, url_uq='https://foo.bar', interval=5, regex='')

    res = DatabaseConnector.get_query_insert_into_table('website', website, True)
    exp = "INSERT INTO website (url_uq, interval) VALUES ('https://foo.bar', 5) ON CONFLICT (url_uq) DO NOTHING;"
    assert clean(res) == clean(exp)

    res = DatabaseConnector.get_query_insert_into_table('website', website, False)
    exp = "INSERT INTO website (website_id, url_uq, interval) VALUES (-1, 'https://foo.bar', 5);"
    assert clean(res) == clean(exp)


    website_with_regex = Website(website_id=-1, url_uq='https://foo.bar', interval=5, regex='welcome')

    res = DatabaseConnector.get_query_insert_into_table('website', website_with_regex, True)
    exp = "INSERT INTO website (url_uq, interval, regex) VALUES ('https://foo.bar', 5, 'welcome') ON CONFLICT (url_uq) DO NOTHING;"
    assert clean(res) == clean(exp)

    res = DatabaseConnector.get_query_insert_into_table('website', website_with_regex, False)
    exp = "INSERT INTO website (website_id, url_uq, interval, regex) VALUES (-1, 'https://foo.bar', 5, 'welcome');"
    assert clean(res) == clean(exp)


