# PyAlgoTrade
#
# Copyright 2011-2015 Gabriel Martin Becedillas Ruiz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
.. moduleauthor:: Gabriel Martin Becedillas Ruiz <gabriel.becedillas@gmail.com>
"""

import datetime
import logging
import pyalgotrade.logger
from pyalgotrade import broker
from pyalgotrade.utils import dt

logger = pyalgotrade.logger.getLogger(name="poloniex")
#logger.setLevel(logging.DEBUG)

CASH_TOKEN = None #must set via setPairInfo()
INSTRUMENT_TOKEN = None #must set via setPairInfo()
CURRENCY_PAIR = None #must set via setPairInfo()

MIN_TRADE_CASH_TOKEN = 0.01147 #about $5 in BTC

CASH_TOKEN_PRECISION = 8 #if cash token is USD, we may have to set this to 2...
INSTRUMENT_TOKEN_PRECISION = 8

DEFAULT_MAKER_FEE = 0.0015
DEFAULT_TAKER_FEE = 0.0025

def setPairInfo(cashTokenName, InstrumentTokenName):
    global CASH_TOKEN, INSTRUMENT_TOKEN, CURRENCY_PAIR
    CASH_TOKEN = cashTokenName
    INSTRUMENT_TOKEN = InstrumentTokenName
    CURRENCY_PAIR = "%s_%s" % (CASH_TOKEN, INSTRUMENT_TOKEN)

class InstrumentTraits(broker.InstrumentTraits):
    def roundQuantity(self, quantity):
        return round(quantity, INSTRUMENT_TOKEN_PRECISION)

def parse_datetime(dateTime):
    try:
        ret = datetime.datetime.strptime(dateTime, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        ret = datetime.datetime.strptime(dateTime, "%Y-%m-%d %H:%M:%S.%f")
    return dt.as_utc(ret)
