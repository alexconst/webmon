#!/usr/bin/env python3

import argparse
import asyncio
import json
import logging
import sys

from webmon.web_monitor import WebMonitor


def setup_logging(level):
    level = logging.getLevelName(level)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s:%(name)s: %(message)s",
        level=level,    # logging.DEBUG,
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def main(argv):
    description = "Monitor list of sites and save metrics in database."
    use_examples = "Examples:"
    use_examples += "\n{} --db-config secrets/db_postgresql.json --sites-csv data/websites_top15.csv --number-healthchecks 5".format(argv[0])
    use_examples += "\n{} --db-config secrets/db_postgresql.json --sites-table --number-healthchecks -1".format(argv[0])
    use_examples += "\n{} --db-config secrets/db_postgresql.json --drop-tables".format(argv[0])

    parser = argparse.ArgumentParser(description=description, epilog=use_examples, formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('--log-level',
                        metavar=('LOG_LEVEL'),
                        nargs=1,
                        default=['INFO'],
                        help='Desired log level. Defaults to INFO. To only view sites that failed healthechecks use ERROR')
    parser.add_argument('--db-config', metavar=('FILENAME_DBCONFIG'), type=str, nargs=1, help='JSON file with DB access secrets and details.')
    parser.add_argument(
        '--sites-csv',
        metavar=('FILENAME_CSV'),
        type=str,
        nargs=1,
        help=
        'CSV file with list of websites to monitor. These will be appended to the existing ones in the DB. Each row includes: URL, time interval in seconds, optional regex.'
    )
    parser.add_argument('--number-healthchecks',
                        metavar=('NUMBER_CHECKS'),
                        type=int,
                        nargs=1,
                        help='Number of healthchecks to perform per websites. For an infinite number use -1.')
    parser.add_argument(
        '--sites-table',
        action='store_true',
        help='For the website checks rules, use the pre-existing information in the DB (eg: which was inserted from a previous execution).')
    parser.add_argument('--drop-tables', action='store_true', help='Drop tables for websites and healthchecks.')

    args = parser.parse_args()
    if len(argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    if not args.db_config:
        print("ERROR: a db config file needs to be provided.")
        sys.exit(1)
    else:
        dbconfig_filename = args.db_config[0]
    if not args.drop_tables and not args.number_healthchecks:
        print("ERROR: the number of healtchecks needs to be provided. Use -1 for infinite number.")
        sys.exit(1)
    elif args.drop_tables:
        number_healthchecks = 0
    else:
        number_healthchecks = int(args.number_healthchecks[0])
    if args.sites_csv:
        sites_filename = args.sites_csv[0]
    else:
        sites_filename = ''

    setup_logging(args.log_level[0])
    wm = WebMonitor(dbconfig_filename, sites_filename, number_healthchecks)
    if args.sites_csv or args.sites_table:
        action = 'monitor'
    if args.drop_tables:
        action = 'drop-tables'
    asyncio.run(wm.run(action))


if __name__ == '__main__':
    main(sys.argv)
