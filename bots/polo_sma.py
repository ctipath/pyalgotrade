
import sys
sys.path.append("/home/local")
sys.path.append("..")
sys.path.append("../..")
import traceback

from pyalgotrade.poloniex import barfeed, broker, common, httpclient
from pyalgotrade import strategy
from pyalgotrade.technical import ma
from pyalgotrade.technical import cross
import sortedcontainers

INSTRUMENT_TOKEN = "ETH"
CASH_TOKEN = "BTC"

class Strategy(strategy.BaseStrategy):
    def __init__(self, feed, brk, live=False):
        super(Strategy, self).__init__(feed, brk)
        self.__httpClient = httpclient.HTTPClient(None, None) #no key and secret for now...
        self.__prices = feed[INSTRUMENT_TOKEN].getCloseDataSeries()
        smaPeriod = 20
        self.__sma = ma.SMA(self.__prices, smaPeriod)
        self.__bidBook = sortedcontainers.SortedDict()
        self.__askBook = sortedcontainers.SortedDict()
        self.__bid = None
        self.__ask = None
        self.__position = None
        self.__posSize = 50

        if live:
            #initially populate orderbook from the exchange...
            self.__bidBook, self.__askBook, self.__bid, self.__ask = self.__httpClient.getLiveOrderBook()

        # Subscribe to order book update events to get bid/ask prices to trade.
        feed.getOrderBookModificationEvent().subscribe(self.__onOrderBookModification)
        feed.getOrderBookRemovalEvent().subscribe(self.__onOrderBookRemoval)

    def __replaceBestOrder(self, orderBookModificationOrRemoval):
        if orderBookModificationOrRemoval.isBid():
            bestBid = reversed(self.__bidBook).next() if len(self.__bidBook) else None
            if bestBid is not None and self.__bid != bestBid:
                self.__bid = bestBid
                self.info("Best (highest) bid is now %s" % (self.__bid))
        else:
            assert orderBookModificationOrRemoval.isAsk()
            bestAsk = iter(self.__askBook).next() if len(self.__askBook) else None
            if bestAsk is not None and self.__ask != bestAsk:
                self.__ask = bestAsk
                self.info("Best (lowest) ask is now %s" % (self.__ask))

    def __onOrderBookModification(self, orderBookModification):
        book = self.__bidBook if orderBookModification.isBid() else self.__askBook
        book[orderBookModification.getPrice()] = orderBookModification.getAmount()
        self.__replaceBestOrder(orderBookModification)

    def __onOrderBookRemoval(self, orderBookRemoval):
        book = self.__bidBook if orderBookRemoval.isBid() else self.__askBook
        book.pop(orderBookRemoval.getPrice(), None)
        self.__replaceBestOrder(orderBookRemoval)

    def onEnterOk(self, position):
        self.info("Position opened at %s" % (position.getEntryOrder().getExecutionInfo().getPrice()))

    def onEnterCanceled(self, position):
        self.info("Position entry canceled")
        self.__position = None

    def onExitOk(self, position):
        self.__position = None
        self.info("Position closed at %s" % (position.getExitOrder().getExecutionInfo().getPrice()))

    def onExitCanceled(self, position):
        # If the exit was canceled, re-submit it.
        self.__position.exitLimit(self.__bid)

    def onBars(self, bars):
        bar = bars[INSTRUMENT_TOKEN]
        self.info("Price: {0:.8f}. Volume: {0:.8f}".format(bar.getClose(), bar.getVolume()))

        # Wait until we get the current bid/ask prices.
        if self.__ask is None:
            return

        # If a position was not opened, check if we should enter a long position.
        if self.__position is None:
            if cross.cross_above(self.__prices, self.__sma) > 0:
                self.info("Entry signal. Buy %s at %s" % (self.__posSize, self.__ask))
                self.__position = self.enterLongLimit(
                    INSTRUMENT_TOKEN, self.__ask, self.__posSize, True)
        # Check if we have to close the position.
        elif not self.__position.exitActive() and cross.cross_below(self.__prices, self.__sma) > 0:
            self.info("Exit signal. Sell at %s" % (self.__bid))
            self.__position.exitLimit(self.__bid)

def main():
    #def log_uncaught_exceptions(ex_cls, ex, tb):
    #    common.logger.critical(''.join(traceback.format_tb(tb)))
    #    common.logger.critical('{0}: {1}'.format(ex_cls, ex))
    #sys.excepthook = log_uncaught_exceptions

    mode = 'live'
    if mode == 'live':
        common.setPairInfo(CASH_TOKEN, INSTRUMENT_TOKEN)
        barFeed = barfeed.LiveTradeFeed()
        brk = broker.PaperTradingBroker(1000, barFeed)
        strat = Strategy(barFeed, brk, live=True)
    else:
        raise NotImplementedError

    strat.run()

if __name__ == "__main__":
    main()

