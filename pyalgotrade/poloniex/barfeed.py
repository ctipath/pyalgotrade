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
import csvutils
import datetime

from pyalgotrade.poloniex import livefeed
from pyalgotrade.barfeed import csvfeed
from pyalgotrade.utils import dt

def to_utc_if_naive(dateTime):
    if dateTime is not None and dt.datetime_is_naive(dateTime):
        dateTime = dt.as_utc(dateTime)
    return dateTime


class PoloniexCSVRowParser(csvfeed.GenericRowParser):
    pass

class PoloniexCSVBarFeed(csvfeed.GenericBarFeed):
    def addBarsFromCSV(self, instrument, path, timezone=None, fromDateTime=None, toDateTime=None):
        if timezone is None:
            timezone = self.__timezone
        rowParser = PoloniexCSVRowParser(self.__columnNames, self.__dateTimeFormat, self.getDailyBarTime(), self.getFrequency(), timezone)

        #startTimestamp = calendar.timegm(startDateTime.utctimetuple()) if startDateTime else None
        #endTimestamp = calendar.timegm(endDateTime.utctimetuple()) if endDateTime else None

        # Save the barfilter to restore it later.
        prevBarFilter = self.getBarFilter()
        try:
            if fromDateTime or toDateTime:
                self.setBarFilter(csvfeed.DateRangeFilter(to_utc_if_naive(fromDateTime), to_utc_if_naive(toDateTime)))
            super(CSVTradeFeed, self).addBarsFromCSV(instrument, path, rowParser)
        finally:
            self.setBarFilter(prevBarFilter)

        assert not rowParser.barsHaveAdjClose()

LiveTradeFeed = livefeed.LiveTradeFeed
