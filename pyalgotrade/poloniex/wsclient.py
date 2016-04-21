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

##REQUIRES trollus and autobahn packages to be installed via pip

import datetime
import Queue
from os import environ
import threading

import sortedcontainers
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
import trollius as asyncio #asyncio is for Python 3+
from trollius import From

from pyalgotrade.poloniex import common, httpclient

WEBSOCKET_HOST = u"wss://api.poloniex.com:443"
WEBSOCKET_REALM = u"realm1"

class Trade(httpclient.Trade):
    pass

class TickerUpdate(object):
    def __init__(self, jsonList):
        self._jsonList = jsonList

    def getList(self):
        return self._jsonList

    def getCurrencyPair(self):
        return self._jsonList[0]

    def getLastPrice(self):
        return self._jsonList[1]

    def getLowestAsk(self):
        return self._jsonList[2]

    def getHighestBid(self):
        return self._jsonList[3]

    def getPercentChange(self):
        return self._jsonList[4]

    def getBaseVolume(self):
        return self._jsonList[5]

    def getQuoteVolume(self):
        return self._jsonList[6]

    def getIsFrozen(self):
        return self._jsonList[7]

    def get24HourHigh(self):
        return self._jsonList[8]

    def get24HourLow(self):
        return self._jsonList[9]

class OrderBookRemoval(object):
    def __init__(self, jsonDict):
        self._jsonDict = jsonDict

    def getDict(self):
        return self._jsonDict

    def isBid(self):
        return self._jsonDict["type"] == "bid"

    def isAsk(self):
        return self._jsonDict["type"] == "ask"

    def getPrice(self):
        return float(self._jsonDict["rate"])

class OrderBookModification(OrderBookRemoval):
    def __init__(self, jsonDict):
        super(OrderBookModification, self).__init__(jsonDict)

    def getAmount(self):
        return float(self._jsonDict["amount"])

class WebSocketClientSession(ApplicationSession):
    BACKLOG_MAX_SIZE = 50 #after this, the entry holding things up will be skipped...

    # Events
    ON_TICKER_UPDATE = 1
    ON_TRADE = 2
    ON_ORDER_BOOK_MODIFY = 3
    ON_ORDER_BOOK_REMOVE = 4
    ON_CONNECTED = 5
    ON_DISCONNECTED = 6

    def __init__(self, *args, **kwargs):
        self.__queue = Queue.Queue()
        self.__lastSeq = None
        self.__seqBacklog = sortedcontainers.SortedDict()
        super(WebSocketClientSession, self).__init__(*args, **kwargs)

    def getQueue(self):
        return self.__queue

    def onConnect(self):
        common.logger.info("Connection established")
        self.config.extra['client']._setSession(self)
        self.__queue.put((WebSocketClientSession.ON_CONNECTED, None))
        self.join(self.config.realm)

    @asyncio.coroutine
    def onJoin(self, details):

        def onTickerUpdate(*event):
            tickerUpdate = TickerUpdate(event)
            if tickerUpdate.getCurrencyPair() != common.CURRENCY_PAIR:
                return #skip as it's not for the currency pair we're monitoring

            common.logger.debug("TICKER: {}".format(event))
            self.__queue.put((WebSocketClientSession.ON_TICKER_UPDATE, tickerUpdate))

        def onOrderBookAndTrades(*events, **kwargs):
            def dispatchEventsInMessage(seq, events):
                for event in events:
                    if event['type'] == u'orderBookModify':
                        common.logger.debug("OBOOK-MODIFY({}): {}".format(seq, event['data']))
                        self.__queue.put((WebSocketClientSession.ON_ORDER_BOOK_MODIFY, OrderBookModification(event['data'])))
                    elif event['type'] == u'orderBookRemove':
                        common.logger.debug("OBOOK-REMOVE({}): {}".format(seq, event['data']))
                        self.__queue.put((WebSocketClientSession.ON_ORDER_BOOK_REMOVE, OrderBookRemoval(event['data'])))
                    else:
                        assert event['type'] == 'newTrade'
                        common.logger.debug("TRADE({}): {}".format(seq, event['data']))
                        self.__queue.put((WebSocketClientSession.ON_TRADE, Trade(event['data'])))

            def dispatchOrBacklogMessage(seq, events):
                if self.__lastSeq:
                    if seq < self.__lastSeq: #older message, discard
                        common.logger.debug("Discarding event sequence ID {} as < lastSeq {}".format(seq, self.__lastSeq))
                        return True
                    elif seq == self.__lastSeq + 1: #in order, process
                        dispatchEventsInMessage(seq, events)
                        self.__lastSeq += 1
                        return True
                    else: #came out of order. backlog it until the earlier message comes
                        if seq in self.__seqBacklog:
                            common.logger.debug("Sequence {} exists in backlog. Replacing...".format(seq))
                        else:
                            common.logger.debug("Backlogging sequence {} ({} events, waiting for seq {} first...)".format(
                                seq, len(events), self.__lastSeq + 1))
                        self.__seqBacklog[seq] = events #replace if exists already

                        if len(self.__seqBacklog) == WebSocketClientSession.BACKLOG_MAX_SIZE:
                            common.logger.info("Backlog has reached its max size of {} waiting for seq {}. Skipping it and catching up".format(
                                WebSocketClientSession.BACKLOG_MAX_SIZE, self.__lastSeq + 1))
                            self.__lastSeq += 1
                            return True
                        else:
                            return False
                else: #first message on connection, go from here...
                    common.logger.debug("Setting backlog sequence start as {}".format(seq))
                    self.__lastSeq = seq
                    dispatchEventsInMessage(seq, events)
                    return True

            assert kwargs['seq']
            if dispatchOrBacklogMessage(kwargs['seq'], events):
                while len(self.__seqBacklog): #clear out as much of our seqBacklog as possible...
                    nextSeq = iter(self.__seqBacklog).next()
                    if dispatchOrBacklogMessage(nextSeq, self.__seqBacklog[nextSeq]):
                        common.logger.debug("Cleared seq {} from backlog".format(nextSeq))
                        del self.__seqBacklog[nextSeq] #loop and start working on the next backlog entry, if present...
                    else:
                        break #can't process further for now

        try:
            yield From(self.subscribe(onTickerUpdate, 'ticker'))
            yield From(self.subscribe(onOrderBookAndTrades, common.CURRENCY_PAIR))
        except Exception as e:
            common.logger.error("Could not subscribe to topic: {}".format(e))

    def onLeave(self, details):
        common.logger.info("Connection left")
        self.disconnect()

    def onDisconnect(self):
        common.logger.info("Connection disconnected")
        self.__queue.put((WebSocketClientSession.ON_DISCONNECTED, None))
        asyncio.get_event_loop().stop()

    def stop(self):
        common.logger.info("Stopping websocket client")
        self.disconnect()

class WebSocketClient(threading.Thread):
    def __init__(self):
        super(WebSocketClient, self).__init__()
        self.__session = None
        self.__mainLoop = asyncio.get_event_loop()
        self.__loop = asyncio.new_event_loop()

    def _setSession(self, session):
        self.__session = session

    def getQueue(self):
        if not self.__session:
            return None #not available yet
        return self.__session.getQueue()

    def start(self):
        #def stopEventLoops():
        #    self.__loop.stop()
        #    if self.__mainLoop.is_running():
        #        self.__mainLoop.stop()

        assert not self.__session

        #hack to avoid txaio double logging...
        import txaio
        txaio.aio._started_logging = True

        #stop the thread's event loop on SIGTERM, so that the application properly terminates on Keyboard abort, etc
        #import signal
        #self.__mainLoop.add_signal_handler(signal.SIGTERM, stopEventLoops)

        super(WebSocketClient, self).start()

    def run(self):
        def childEventLoopSigHandler(sig, func):
            raise NotImplementedError

        assert not self.__session
        asyncio.set_event_loop(self.__loop)

        #hack so that autobahn doesn't try to bind SIGTERM to the thread's event loop (which would generate an exception)
        self.__loop.add_signal_handler = childEventLoopSigHandler

        runner = ApplicationRunner(WEBSOCKET_HOST, WEBSOCKET_REALM, extra={'client': self})
        runner.run(WebSocketClientSession)

    def stop(self):
        if not self.__session:
            common.logger.warning("websocket client already stopped...")
            return

        try:
            self.__session.stop()
        except Exception, e:
            common.logger.error("Error stopping websocket client: %s." % (str(e)))
        self.__session = None
