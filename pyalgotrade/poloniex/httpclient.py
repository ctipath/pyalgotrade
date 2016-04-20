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
import time
import datetime
import calendar
from datetime import datetime

from pyalgotrade.utils import dt
from pyalgotrade.poloniex import common, poloapi

import logging


class AccountBalance(object):
    def __init__(self, jsonDict):
        self._jsonDict = jsonDict

    def getDict(self):
        return self._jsonDict

    def getCashTokenAvailable(self):
        return float(self._jsonDict[common.CASH_TOKEN])

    def getInstrumentTokenAvailable(self):
        return float(self._jsonDict[common.INSTRUMENT_TOKEN])


class Order(object):
    def __init__(self, jsonDict):
        self._jsonDict = jsonDict

    def getDict(self):
        return self._jsonDict

    def getId(self):
        return int(self._jsonDict.get("orderNumber", self._jsonDict["tradeID"]))

    def isBuy(self):
        return self._jsonDict["type"] == "buy"

    def isSell(self):
        return self._jsonDict["type"] == "sell"

    def getPrice(self):
        return float(self._jsonDict["rate"])

    def getAmount(self):
        return float(self._jsonDict["amount"])

    def getTotal(self):
        return float(self._jsonDict["total"])

    def getDateTime(self):
        return common.parse_datetime(self._jsonDict["date"])

class Trade(Order):
    def __init__(self, jsonDict, feeDict=None):
        super(Trade, self).__init__(jsonDict)
        self.__feeDict = feeDict

    def getFee(self):
        if self.__feeDict:
            return float(self.__feeDict['makerFee']) if self.isSell() else float(self.__feeDict['takerFee'])
        else:
            return common.DEFAULT_MAKER_FEE if self.isSell() else common.DEFAULT_TAKER_FEE

class HTTPClient(object):
    def __init__(self, key, secret):
        self.__client = poloapi.poloniex(key, secret)
        self.__feeDict = self.__client.returnFeeInfo()

    def getAccountBalance(self):
        jsonResponse = self.__client.returnBalances()
        return AccountBalance(jsonResponse)

    def getOpenOrders(self):
        """Gets the user's open order listing"""
        jsonResponse = self.__client.returnOpenOrders(common.CURRENCY_PAIR)
        return [Order(json_open_order) for json_open_order in jsonResponse]

    def cancelOrder(self, orderId):
        jsonResponse = self.__client.cancel(common.CURRENCY_PAIR, orderId)
        if jsonResponse['success'] != 1:
            raise Exception("Failed to cancel order %s" % orderId)

    def buyLimit(self, limitPrice, quantity):
        price = round(limitPrice, common.INSTRUMENT_TOKEN_PRECISION)
        amount = round(quantity, common.INSTRUMENT_TOKEN_PRECISION)

        jsonResponse = self.__client.buy(common.CURRENCY_PAIR, limitPrice, quantity)
        return jsonResponse['orderNumber']

    def sellLimit(self, limitPrice, quantity):
        price = round(limitPrice, common.INSTRUMENT_TOKEN_PRECISION)
        amount = round(quantity, common.INSTRUMENT_TOKEN_PRECISION)

        jsonResponse = self.__client.sell(common.CURRENCY_PAIR, limitPrice, quantity)
        return jsonResponse['orderNumber']

    def getTradeHistory(self, startDateTime=None):
        """Gets the user's trade history"""
        #convert startDateTime into UNIX timestamp
        startTimestamp = calendar.timegm(startDateTime.utctimetuple()) if startDateTime else None
        jsonResponse = self.__client.returnTradeHistory(common.CURRENCY_PAIR, start=startTimestamp)
        return [Trade(json_trade, feeDict=self.__feeDict) for json_trade in jsonResponse]
