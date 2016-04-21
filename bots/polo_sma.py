
import sys
sys.path.append("/home/local")
sys.path.append("..")
sys.path.append("../..")
import traceback

from pyalgotrade.poloniex import barfeed, broker, common, poloapi
from pyalgotrade import strategy
from pyalgotrade.technical import ma
from pyalgotrade.technical import cross
from sortedcontainers import SortedDict

INSTRUMENT_TOKEN = "ETH"
CASH_TOKEN = "BTC"

class Strategy(strategy.BaseStrategy):
    def __init__(self, feed, brk):
        super(Strategy, self).__init__(feed, brk)
        self.__bidBook = SortedDict()
        self.__askBook = SortedDict()
        smaPeriod = 20
        self.__prices = feed[INSTRUMENT_TOKEN].getCloseDataSeries()
        self.__sma = ma.SMA(self.__prices, smaPeriod)
        self.__bid = None
        self.__ask = None
        self.__position = None
        self.__posSize = 50
        self.__noAuthHTTPClient = poloapi.poloniex(None, None)

        #initially populate orderbook
        self.__populateOrderBookInitially()

        # Subscribe to order book update events to get bid/ask prices to trade.
        feed.getOrderBookModificationEvent().subscribe(self.__onOrderBookModification)
        feed.getOrderBookRemovalEvent().subscribe(self.__onOrderBookRemoval)

    def __populateOrderBookInitially(self):
        orderBook = self.__noAuthHTTPClient.returnOrderBook(common.CURRENCY_PAIR)
        for i in xrange(len(orderBook['bids'])):
            bid = orderBook['bids'][i]
            self.__bidBook[float(bid[0])] = float(bid[1])
            if i == 0:
                self.__bid = float(bid[0])
        for i in xrange(len(orderBook['asks'])):
            ask = orderBook['asks'][i]
            self.__askBook[float(ask[0])] = float(ask[1])
            if i == 0:
                self.__ask = float(ask[0])
        common.logger.info("Orderbook initially populated. %s bids (best: %s), %s asks (best: %s)" % (
            len(self.__bidBook), reversed(self.__bidBook).next(), len(self.__askBook), iter(self.__askBook).next()))

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

    common.setPairInfo(CASH_TOKEN, INSTRUMENT_TOKEN)
    barFeed = barfeed.LiveTradeFeed()
    brk = broker.PaperTradingBroker(1000, barFeed)
    strat = Strategy(barFeed, brk)

    strat.run()

if __name__ == "__main__":
    main()

