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
import trollius as asyncio #asyncio is for Python 3+
from trollius import From
from os import environ
import threading
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner

from pyalgotrade.poloniex import common, httpclient

WEBSOCKET_HOST = u"wss://api.poloniex.com:443"
WEBSOCKET_REALM = u"realm1"

class Trade(httpclient.Trade):
    pass

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
    # Events
    ON_TRADE = 1
    ON_ORDER_BOOK_MODIFY = 2
    ON_ORDER_BOOK_REMOVE = 3
    ON_CONNECTED = 4
    ON_DISCONNECTED = 5

    def __init__(self, *args, **kwargs):
        self.__queue = Queue.Queue()
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

        def onTicker(*event):
            common.logger.debug("TICKER: {}".format(event))

        def onOrderBookAndTrades(*events, **kwargs):
            for event in events:
                if event['type'] == u'orderBookModify':
                    common.logger.debug("OBOOK-MODIFY({}): {}".format(kwargs['seq'], event['data']))
                    self.__queue.put((WebSocketClientSession.ON_ORDER_BOOK_MODIFY, OrderBookModification(event['data'])))
                elif event['type'] == u'orderBookRemove':
                    common.logger.debug("OBOOK-REMOVE({}): {}".format(kwargs['seq'], event['data']))
                    self.__queue.put((WebSocketClientSession.ON_ORDER_BOOK_REMOVE, OrderBookRemoval(event['data'])))
                else:
                    assert event['type'] == 'newTrade'
                    common.logger.debug("TRADE({}): {}".format(kwargs['seq'], event['data']))
                    self.__queue.put((WebSocketClientSession.ON_TRADE, Trade(event['data'])))
        try:
            yield From(self.subscribe(onTicker, 'ticker'))
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
