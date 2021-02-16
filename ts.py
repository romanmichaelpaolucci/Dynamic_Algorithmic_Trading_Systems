from ibapi.wrapper import EWrapper
from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.order import Order
from ibapi.utils import iswrapper
import threading
import abc
import time


class Controller(EWrapper, EClient):

    @iswrapper
    def error(self, reqId, errorCode, errorString):
        print(errorString)

    @iswrapper
    def connectAck(self):
        print("\n[Connected]")
        self.connected = True

    @iswrapper
    def nextValidId(self, orderId):
        self.order_id = orderId

    @iswrapper
    def tickPrice(self, reqId, tickType, price, attrib):
        super().tickPrice(reqId, tickType, price, attrib)
        # Responsible for setting the last price reference field for a system
        if reqId == 1000:
            if tickType == 4:  # Last Trading Price
                self.nasdaq_last_price = price

    def getNewOrderId(self):
        self.order_id += 1
        return self.order_id

    def __init__(self):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)

        # Reference Fields
        self.connected = False
        self.order_id = 0
        self.nasdaq_last_price = 0


class TradingSystem(abc.ABC):

    @abc.abstractmethod
    def trading_signal(self):
        pass

    @abc.abstractmethod
    def execute_trade(self):
        pass

    @abc.abstractmethod
    def run_system(self):
        pass

    def __init__(self, controller, system_id, request_ids):
        self.controller = controller
        self.system_id = system_id
        self.request_ids = request_ids
        thread = threading.Thread(target=self.run_system)
        thread.start()


class NasdaqTradingSystem(TradingSystem):

    def trading_signal(self):
        if not self.active_order:
            print('System ', self.system_id, ': Buy Executed')
            self.execute_trade('BOT')
        else:
            print('System ', self.system_id, ': Sell Executed')
            self.execute_trade('SLD')

    def execute_trade(self, position_type):
        if position_type == 'BOT':
            # Enter a long position
            order = Order()
            order.action = "BUY"
            order.orderType = "MKT"
            order.totalQuantity = 1
            self.buy_price = self.controller.nasdaq_last_price  # For Proft Ref
            self.instance_order_id = self.controller.getNewOrderId()  # For system order reference (potential cancellation etc...)
            self.active_order = True
            self.controller.placeOrder(self.instance_order_id, self.contract, order)
        elif position_type == 'SLD':
            # Check for profit and potentially execute a sell order
            if self.buy_price < self.controller.nasdaq_last_price:
                order = Order()
                order.action = "SELL"
                order.orderType = "MKT"
                order.totalQuantity = 1
                self.buy_price = 0
                self.instance_order_id = self.controller.getNewOrderId()  # For system order reference (potential cancellation etc...)
                self.active_order = False
                self.controller.placeOrder(self.instance_order_id, self.contract, order)
            else:
                print('System ', self.system_id, ': No Profit, Holding')
                # Hold another 10 seconds
                pass

    def run_system(self):
        while(True):
            if self.controller.connected and self.controller.nasdaq_last_price == 0:
                self.controller.reqMktData(self.request_ids['MktDataId'], self.contract, "", False, False, [])
            if not self.controller.nasdaq_last_price == 0:  # Implies Live Data
                print('System ', self.system_id, ': Trading Signal Call')
                self.trading_signal()
            time.sleep(10)

    def __init__(self, controller, system_id, request_ids):
        self.buy_price = 0
        self.active_order = False
        self.instance_order_id = 0
        self.contract = Contract()
        self.contract.symbol = "NQ"
        self.contract.localSymbol = "NQH1"
        self.contract.secType = "FUT"
        self.contract.exchange = "GLOBEX"
        self.contract.currency = "USD"
        super().__init__(controller, system_id, request_ids)

def main():
    controller = Controller()
    nasdaq_request_ids = {'MktDataId': 1000}
    nasdaq_trading_system = NasdaqTradingSystem(controller, 'Nasdaq A', nasdaq_request_ids)
    controller.connect('127.0.0.1', 7497, 0)
    controller.reqMarketDataType(1)
    controller.reqAllOpenOrders()
    controller.run()


if __name__ == "__main__":
    main()
