#/usr/bin/python
import sys
sys.path += ["/home/local", "..", "../.."]
import os
import json
import readline
import datetime
import time
import calendar
import csv
import re
from dateutil import parser as date_parser

from pyalgotrade.poloniex import poloapi

#CSV FILE NAMING: poloniex-BTC_XCP-300.csv
FILENAME_PREFIX = "poloniex"

def usage():
    print("SYNTAX 1: %s CURRENCY_PAIR PERIOD" % sys.argv[0])
    print("SYNTAX 2: %s CSV_FILE" % sys.argv[0])
    print(" * CSV_PATH = The path to an earlier CSV file created by this program")
    print(" * CURRENCY_PAIR = Specify this along with PERIOD to create a new file. A value like BTC_XMR or BTC_ETH")
    print(" * PERIOD = The candlestick period. Specify this instead of CSV_PATH to create a new file.")
    print("   Valid PERIOD values are 300, 900, 1800, 7200, 14400, 86400")

if len(sys.argv) not in [2, 3]:
    usage()
    sys.exit(1)

currency_pair, period, csv_path = None, None, None
if len(sys.argv) == 3: #syntax 1
    try:
        currency_pair = sys.argv[1]
        period = int(sys.argv[2])
    except:
        print("Invalid period or currency pair")
        sys.exit(1)
else: #syntax 2
    try:
        csv_path = sys.argv[1]
        filename_prefix, currency_pair, period = os.path.splitext(os.path.basename(csv_path))[0].split('-')
        period = int(period)
        assert filename_prefix == FILENAME_PREFIX
    except:
        print("Invalid CSV filename, or not existent. E.g. use {}-BTC_XCP-300.csv".format(FILENAME_PREFIX))
        sys.exit(1)

if not bool(re.match("[A-Z]{3}_[A-Z]{3}", currency_pair)):
    print("Invalid currency pair")
    usage()
    sys.exit(1)
if period not in (300, 900, 1800, 7200, 14400, 86400):
    print("Invalid period")
    usage()
    sys.exit(1)
if csv_path and not os.path.exists(csv_path):
    print("CSV file specified does not exist")
    usage()
    sys.exit(1)
if not csv_path:
    last_date, last_date_ts = None, None
    csv_path = '{}-{}-{}.csv'.format(FILENAME_PREFIX, currency_pair, period) #create a new file
    if os.path.exists(csv_path):
        print("CSV file already exists: {}. Using that...".format(csv_path))
if os.path.exists(csv_path):
    #get the last line and continue from there
    with open(csv_path, 'rb') as csv_file:
        csv_file.seek(-4096, 2)
        last_line = csv_file.readlines()[-1].decode()
        last_date_string = last_line.split(',')[0]
        last_date = date_parser.parse(last_date_string + ' -0000')
        last_date_ts = calendar.timegm(datetime.datetime.timetuple(last_date))

#pull in the OHLC data newer than what we have (or, all of the data available if last_date is None)
api_client = poloapi.poloniex(None, None)
print("Contacting server to retrieve {} market history {}, with a {} second period...".format(
    currency_pair, "since {}".format(last_date) if last_date else "for all dates", period))
ohlc_data = api_client.returnChartData(currency_pair, period, start_ts=last_date_ts + 1 if last_date_ts else None)

if len(ohlc_data) and ohlc_data[0]['date'] != 0:
    num_new_rows = len(ohlc_data)
else:
    num_new_rows = 0
print("Retrieved {} rows to process...".format(num_new_rows))

if num_new_rows:
    #add the new ohlc data to the csv
    csv_needs_header = not os.path.exists(csv_path)
    with open(csv_path, 'ab+') as f:
        if csv_needs_header:
            f.write("Date Time,Open,High,Low,Close,Volume,Adj Close\n")
        for row in ohlc_data:
            dt_string = datetime.datetime.utcfromtimestamp(row['date']).strftime("%Y-%m-%d %H:%M:%S")
            f.write(','.join([dt_string, str(row['open']), str(row['high']),
                             str(row['low']), str(row['close']), str(row['volume']), '']) + "\n")

print("All done, processed {} new rows to file {}".format(num_new_rows, csv_path))
