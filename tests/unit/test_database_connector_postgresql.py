import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '../../src/'))
from webmon.database_connector_postgresql import DatabaseConnectorPostgresql
from webmon.healthcheck import Healthcheck, RegexMatchStatus
from webmon.website import Website


def clean(text):
    return text.replace('\n', ' ').replace('  ', ' ').strip(' ')


def test_get_query_create_table():
    website = Website(website_id=-1, url_uq='https://foo.bar', interval=5, regex='')

    res = DatabaseConnectorPostgresql.get_query_create_table('website', website, True)
    exp = 'CREATE TABLE IF NOT EXISTS website (\nwebsite_id SERIAL,\nurl_uq TEXT UNIQUE,\ninterval INT,\nregex TEXT,\nPRIMARY KEY (website_id)\n);'
    assert clean(res) == clean(exp)

    res = DatabaseConnectorPostgresql.get_query_create_table('website', website, False)
    exp = 'CREATE TABLE IF NOT EXISTS website (\nwebsite_id INT,\nurl_uq TEXT,\ninterval INT,\nregex TEXT);'
    assert clean(res) == clean(exp)

    check = Healthcheck(check_id=123,
                        website_fk=33,
                        request_timestamp=1718055080.050827,
                        response_time=3.14,
                        http_status_code=200,
                        regex_match_status=RegexMatchStatus.OK,
                        error_message='')
    res = DatabaseConnectorPostgresql.get_query_create_table('healthcheck', check, True)
    exp = 'CREATE TABLE IF NOT EXISTS healthcheck (\ncheck_id SERIAL,\nwebsite_fk INT,\nrequest_timestamp FLOAT,\nresponse_time FLOAT,\nhttp_status_code INT,\nregex_match_status INT,\nerror_message TEXT,\nPRIMARY KEY (check_id)\n);'
    assert clean(res) == clean(exp)


def test_get_query_drop_table():
    website = Website(website_id=-1, url_uq='https://foo.bar', interval=5, regex='')

    res = DatabaseConnectorPostgresql.get_query_drop_table('website')
    exp = 'DROP TABLE IF EXISTS website;'
    assert clean(res) == clean(exp)


def test_get_querypair_insert_many_into_table():
    website1 = Website(website_id=-1, url_uq='https://foo.bar', interval=5, regex='')
    website2 = Website(website_id=-1, url_uq='https://matrix.bar', interval=10, regex='neo')
    websites = [website1, website2]

    res_query, res_data = DatabaseConnectorPostgresql.get_query_insert_many_into_table('website', websites, True)
    exp_query = 'INSERT INTO website (url_uq, interval, regex) VALUES ($1, $2, $3) ON CONFLICT (url_uq) DO NOTHING;'
    exp_data = [('https://foo.bar', 5, ''), ('https://matrix.bar', 10, 'neo')]
    assert res_query == exp_query
    assert res_data == exp_data
