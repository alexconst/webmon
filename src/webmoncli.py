#!/usr/bin/env python3

import sys
import argparse
import json
import ipdb
import logging
from webmon.web_monitor import WebMonitor


def setup_logging(level):
    level = logging.getLevelName(level)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
        level=level, # logging.DEBUG,
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

def main(argv):
    description = "Monitor list of sites and save metrics in database"
    use_examples = "Examples:"
    use_examples += "\n{} --db-config secrets/db_postgresql.json --sites-csv data/websites_top15.csv".format(argv[0])
    use_examples += "\n{} --db-config secrets/db_postgresql.json --sites-schema sites.json ".format(argv[0])

    parser = argparse.ArgumentParser(description=description, epilog=use_examples, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        '--log-level',
        metavar=('LOG_LEVEL'),
        type=str,
        nargs=1,
        default=logging.INFO,
        help='Desired log level. Defaults to INFO')
    parser.add_argument(
        '--db-config',
        metavar=('FILENAME_DBCONFIG'),
        type=str,
        nargs=1,
        help='JSON file with DB access secrets and details.')
    parser.add_argument(
        '--sites-csv',
        metavar=('FILENAME_CSV'),
        type=str,
        nargs=1,
        help='CSV file with list of websites to check. Each row includes: URL, time interval in seconds, optional regex.')
    parser.add_argument(
        '--sites-schema',
        metavar=('FILENAME_SCHEMA'),
        type=str,
        nargs=1,
        help='JSON file with schema information on how to get the site list from the DB. Includes: db name, db table name, row name for each field.')

    args = parser.parse_args()
    if len(argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if not args.db_config:
        print("ERROR: a db config file needs to be provided.")
        sys.exit(1)
    if not args.sites_csv and not args.sites_schema:
        print("ERROR: either a csv file or a schema file also needs to be provided.")
        sys.exit(1)
    dbconfig_filename = args.db_config[0]
    if args.sites_csv:
        sites_filename = args.sites_csv[0]
    else:
        sites_filename = args.sites_schema[0]

    setup_logging(args.log_level)
    wm = WebMonitor(dbconfig_filename, sites_filename)
    wm.run()


if __name__ == '__main__':
    main(sys.argv)


