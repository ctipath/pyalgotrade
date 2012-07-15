# PyAlgoTrade
# 
# Copyright 2011 Gabriel Martin Becedillas Ruiz
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

import unittest
import datetime
import os

from pyalgotrade.barfeed import csvfeed
import common

class YahooTestCase(unittest.TestCase):
	TestInstrument = "orcl"

	def __parseDate(self, date):
		parser = csvfeed.YahooRowParser()
		row = {"Date":date, "Close":0, "Open":0 , "High":0 , "Low":0 , "Volume":0 , "Adj Close":0}
		return parser.parseBar(row).getDateTime()

	def testParseDate_1(self):
		date = self.__parseDate("1950-1-1")
		self.assertTrue(date.day == 1)
		self.assertTrue(date.month == 1)
		self.assertTrue(date.year == 1950)

	def testParseDate_2(self):
		date = self.__parseDate("2000-1-1")
		self.assertTrue(date.day == 1)
		self.assertTrue(date.month == 1)
		self.assertTrue(date.year == 2000)

	def testDateCompare(self):
		self.assertTrue(self.__parseDate("2000-1-1") == self.__parseDate("2000-1-1"))
		self.assertTrue(self.__parseDate("2000-1-1") != self.__parseDate("2001-1-1"))
		self.assertTrue(self.__parseDate("1999-1-1") < self.__parseDate("2001-1-1"))
		self.assertTrue(self.__parseDate("2011-1-1") > self.__parseDate("2001-2-2"))

	def testCSVFeedLoadOrder(self):
		class BarFeedEventHandler:
			def __init__(self, testcase, barFeed):
				self.__testcase = testcase
				self.__count = 0
				self.__prevDateTime = None
				self.__barFeed = barFeed

			def onBars(self, bars):
				self.__count += 1
				dateTime = bars.getBar(YahooTestCase.TestInstrument).getDateTime()
				if self.__prevDateTime != None:
					# Check that bars are loaded in order
					self.__testcase.assertTrue(self.__prevDateTime < dateTime)
					# Check that the last value in the dataseries match the current datetime.
					self.__testcase.assertTrue(self.__barFeed.getDataSeries().getValue().getDateTime() == dateTime)
				self.__prevDateTime = dateTime

			def getEventCount(self):
				return self.__count

		barFeed = csvfeed.YahooFeed()
		barFeed.addBarsFromCSV(YahooTestCase.TestInstrument, common.get_data_file_path("orcl-2000-yahoofinance.csv"))
		barFeed.addBarsFromCSV(YahooTestCase.TestInstrument, common.get_data_file_path("orcl-2001-yahoofinance.csv"))

		# Dispatch and handle events.
		handler = BarFeedEventHandler(self, barFeed)
		barFeed.getNewBarsEvent().subscribe(handler.onBars)
		while not barFeed.stopDispatching():
			barFeed.dispatch()
		self.assertTrue(handler.getEventCount() > 0)

	def __testFilteredRangeImpl(self, fromDate, toDate, year):
		class BarFeedEventHandler:
			def __init__(self, testcase, year):
				self.__testcase = testcase
				self.__count = 0
				self.__year = year

			def onBars(self, bars):
				self.__count += 1
				self.__testcase.assertTrue(bars.getBar(YahooTestCase.TestInstrument).getDateTime().year == self.__year)

			def getEventCount(self):
				return self.__count

		barFeed = csvfeed.YahooFeed()
		barFeed.setBarFilter(csvfeed.DateRangeFilter(fromDate, toDate))
		barFeed.addBarsFromCSV(YahooTestCase.TestInstrument, common.get_data_file_path("orcl-2000-yahoofinance.csv"))
		barFeed.addBarsFromCSV(YahooTestCase.TestInstrument, common.get_data_file_path("orcl-2001-yahoofinance.csv"))

		# Dispatch and handle events.
		handler = BarFeedEventHandler(self, year)
		barFeed.getNewBarsEvent().subscribe(handler.onBars)
		while not barFeed.stopDispatching():
			barFeed.dispatch()
		self.assertTrue(handler.getEventCount() > 0)

	def testFilteredRangeFrom(self):
		# Only load bars from year 2001.
		self.__testFilteredRangeImpl(datetime.date(2001, 1, 1), None, 2001)

	def testFilteredRangeTo(self):
		# Only load bars up to year 2000.
		self.__testFilteredRangeImpl(None, datetime.date(2000, 12, 31), 2000)

	def testFilteredRangeFromTo(self):
		# Only load bars in year 2000.
		self.__testFilteredRangeImpl(datetime.date(2000, 1, 1), datetime.date(2000, 12, 31), 2000)

def getTestCases():
	ret = []
	ret.append(YahooTestCase("testParseDate_1"))
	ret.append(YahooTestCase("testParseDate_2"))
	ret.append(YahooTestCase("testDateCompare"))
	ret.append(YahooTestCase("testCSVFeedLoadOrder"))
	ret.append(YahooTestCase("testFilteredRangeFrom"))
	ret.append(YahooTestCase("testFilteredRangeTo"))
	ret.append(YahooTestCase("testFilteredRangeFromTo"))
	return ret

