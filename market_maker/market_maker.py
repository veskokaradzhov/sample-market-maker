from __future__ import absolute_import
from time import sleep
import sys
from datetime import datetime
from os.path import getmtime
import random
import requests
import atexit
import signal

# from market_maker import bitmex
from market_maker.settings import settings
from market_maker.utils import log, constants, errors, math
from market_maker.exchange_interface import ExchangeInterface

# Used for reloading the bot - saves modified times of key files
import os


# watched_files_mtimes = [(f, getmtime(f)) for f in settings.WATCHED_FILES]

#
# Helpers
#


class OrderManager:
    def __init__(self):
        self.logger = log.setup_custom_logger('OrderManager')
        self.exchange = ExchangeInterface(settings.DRY_RUN)
        # Once exchange is created, register exit handler that will always cancel orders
        # on any error.
        atexit.register(self.exit)
        signal.signal(signal.SIGTERM, self.exit)

        self.logger.info("Using symbol %s." % self.exchange.symbol)

        if settings.DRY_RUN:
            self.logger.info("Initializing dry run. Orders printed below represent what would be posted to BitMEX.")
        else:
            self.logger.info("Order Manager initializing, connecting to BitMEX. Live run: executing real trades.")

        self.start_time = datetime.now()
        self.instrument = self.exchange.get_instrument()
        self.starting_qty = self.exchange.get_delta()
        self.running_qty = self.starting_qty
        self.reset()

    def reset(self):
        self.exchange.cancel_all_orders()
        self.sanity_check()
        self.print_status()

        # Create orders and converge.
        # self.place_orders()

    def estimate_trade_intensity(self, trades):

        buy_trades = [trade for trade in trades if trade['side'] == 'Buy']
        sell_trades = [trade for trade in trades if trade['side'] == 'Sell']
        buy_trades_timestamps = [datetime.strptime(x['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ') for x in buy_trades]
        sell_trades_timestamps = [datetime.strptime(x['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ') for x in sell_trades]

        buy_trades_sizes = [x['size'] for x in buy_trades]
        sell_trades_sizes = [x['size'] for x in sell_trades]

        buy_trades_timestamps = sorted(buy_trades_timestamps)
        sell_trades_timestamps = sorted(sell_trades_timestamps)
        self.logger.info('buy_trades: {}'.format(buy_trades))
        self.logger.info('sell_trades: {}'.format(sell_trades))
        self.logger.info('buy_trades_timestamps: {}'.format(buy_trades_timestamps))
        self.logger.info('sell_trades_timestamps: {}'.format(sell_trades_timestamps))
        self.logger.info('buy_trades_sizes: {}'.format(buy_trades_sizes))
        self.logger.info('sell_trades_sizes: {}'.format(sell_trades_timestamps))

        waiting_times_seconds_buys = [(t - s).total_seconds() for s, t in
                                      zip(buy_trades_timestamps, buy_trades_timestamps[1:])]
        waiting_times_seconds_sells = [(t - s).total_seconds() for s, t in
                                       zip(sell_trades_timestamps, sell_trades_timestamps[1:])]
        self.logger.info('waiting_times_seconds_buys: {}'.format(waiting_times_seconds_buys))
        self.logger.info('waiting_times_seconds_sells: {}'.format(waiting_times_seconds_sells))

        lambda_buy_arrivals = math.estimate_exponential_lambda(waiting_times_seconds_buys)
        lambda_sell_arrivals = math.estimate_exponential_lambda(waiting_times_seconds_sells)

        self.logger.info('lambda_buy_arrivals: {}'.format(lambda_buy_arrivals))
        self.logger.info('lambda_sell_arrivals: {}'.format(lambda_sell_arrivals))

        lambda_buy_sizes = math.estimate_exponential_lambda(buy_trades_sizes)
        lambda_sell_sizes = math.estimate_exponential_lambda(sell_trades_sizes)

        self.logger.info('lambda_buy_sizes: {}'.format(lambda_buy_sizes))
        self.logger.info('lambda_sell_sizes: {}'.format(lambda_sell_sizes))

        return lambda_buy_arrivals, lambda_sell_arrivals

    def print_status(self):
        """Print the current MM status."""

        margin = self.exchange.get_margin()
        position = self.exchange.get_position()
        self.running_qty = self.exchange.get_delta()
        tickLog = self.exchange.get_instrument()['tickLog']
        self.start_XBt = margin["marginBalance"]

        order_book = self.exchange.bitmex.market_depth()
        self.logger.info('Order Book: {}'.format(order_book))

        trades = self.exchange.recent_trades()

        self.logger.info('Recent Trades: {}'.format(trades))
        self.logger.info('Number of Trades: {}'.format(len(trades)))

        self.estimate_trade_intensity(trades)

        self.logger.info("Current XBT Balance: %.6f" % XBt_to_XBT(self.start_XBt))
        self.logger.info("Current Contract Position: %d" % self.running_qty)
        if settings.CHECK_POSITION_LIMITS:
            self.logger.info("Position limits: %d/%d" % (settings.MIN_POSITION, settings.MAX_POSITION))
        if position['currentQty'] != 0:
            self.logger.info("Avg Cost Price: %.*f" % (tickLog, float(position['avgCostPrice'])))
            self.logger.info("Avg Entry Price: %.*f" % (tickLog, float(position['avgEntryPrice'])))
        self.logger.info("Contracts Traded This Run: %d" % (self.running_qty - self.starting_qty))
        self.logger.info("Total Contract Delta: %.4f XBT" % self.exchange.calc_delta()['spot'])

    def get_ticker(self):
        ticker = self.exchange.get_ticker()
        tickLog = self.exchange.get_instrument()['tickLog']

        # Set up our buy & sell positions as the smallest possible unit above and below the current spread
        # and we'll work out from there. That way we always have the best price but we don't kill wide
        # and potentially profitable spreads.
        self.start_position_buy = ticker["buy"] + self.instrument['tickSize']
        self.start_position_sell = ticker["sell"] - self.instrument['tickSize']

        # If we're maintaining spreads and we already have orders in place,
        # make sure they're not ours. If they are, we need to adjust, otherwise we'll
        # just work the orders inward until they collide.
        if settings.MAINTAIN_SPREADS:
            if ticker['buy'] == self.exchange.get_highest_buy()['price']:
                self.start_position_buy = ticker["buy"]
            if ticker['sell'] == self.exchange.get_lowest_sell()['price']:
                self.start_position_sell = ticker["sell"]

        # Back off if our spread is too small.
        if self.start_position_buy * (1.00 + settings.MIN_SPREAD) > self.start_position_sell:
            self.start_position_buy *= (1.00 - (settings.MIN_SPREAD / 2))
            self.start_position_sell *= (1.00 + (settings.MIN_SPREAD / 2))

        # Midpoint, used for simpler order placement.
        self.start_position_mid = ticker["mid"]
        self.logger.info(
            "%s Ticker: Buy: %.*f, Sell: %.*f" %
            (self.instrument['symbol'], tickLog, ticker["buy"], tickLog, ticker["sell"])
        )
        self.logger.info('Start Positions: Buy: %.*f, Sell: %.*f, Mid: %.*f' %
                         (tickLog, self.start_position_buy, tickLog, self.start_position_sell,
                          tickLog, self.start_position_mid))
        return ticker

    def get_price_offset(self, index):
        """Given an index (1, -1, 2, -2, etc.) return the price for that side of the book.
           Negative is a buy, positive is a sell."""
        # Maintain existing spreads for max profit
        if settings.MAINTAIN_SPREADS:
            start_position = self.start_position_buy if index < 0 else self.start_position_sell
            # First positions (index 1, -1) should start right at start_position, others should branch from there
            index = index + 1 if index < 0 else index - 1
        else:
            # Offset mode: ticker comes from a reference exchange and we define an offset.
            start_position = self.start_position_buy if index < 0 else self.start_position_sell

            # If we're attempting to sell, but our sell price is actually lower than the buy,
            # move over to the sell side.
            if index > 0 and start_position < self.start_position_buy:
                start_position = self.start_position_sell
            # Same for buys.
            if index < 0 and start_position > self.start_position_sell:
                start_position = self.start_position_buy

        return math.to_nearest(start_position * (1 + settings.INTERVAL) ** index, self.instrument['tickSize'])

    ###
    # Orders
    ###

    def place_orders(self):
        """Create order items for use in convergence."""

        buy_orders = []
        sell_orders = []
        # Create orders from the outside in. This is intentional - let's say the inner order gets taken;
        # then we match orders from the outside in, ensuring the fewest number of orders are amended and only
        # a new order is created in the inside. If we did it inside-out, all orders would be amended
        # down and a new order would be created at the outside.
        for i in reversed(range(1, settings.ORDER_PAIRS + 1)):
            if not self.long_position_limit_exceeded():
                buy_orders.append(self.prepare_order(-i))
            if not self.short_position_limit_exceeded():
                sell_orders.append(self.prepare_order(i))

        return self.converge_orders(buy_orders, sell_orders)

    def prepare_order(self, index):
        """Create an order object."""

        if settings.RANDOM_ORDER_SIZE is True:
            quantity = random.randint(settings.MIN_ORDER_SIZE, settings.MAX_ORDER_SIZE)
        else:
            quantity = settings.ORDER_START_SIZE + ((abs(index) - 1) * settings.ORDER_STEP_SIZE)

        price = self.get_price_offset(index)

        return {'price': price, 'orderQty': quantity, 'side': "Buy" if index < 0 else "Sell"}

    def converge_orders(self, buy_orders, sell_orders):
        """Converge the orders we currently have in the book with what we want to be in the book.
           This involves amending any open orders and creating new ones if any have filled completely.
           We start from the closest orders outward."""

        tickLog = self.exchange.get_instrument()['tickLog']
        to_amend = []
        to_create = []
        to_cancel = []
        buys_matched = 0
        sells_matched = 0
        existing_orders = self.exchange.get_orders()

        # Check all existing orders and match them up with what we want to place.
        # If there's an open one, we might be able to amend it to fit what we want.
        for order in existing_orders:
            try:
                if order['side'] == 'Buy':
                    desired_order = buy_orders[buys_matched]
                    buys_matched += 1
                else:
                    desired_order = sell_orders[sells_matched]
                    sells_matched += 1

                # Found an existing order. Do we need to amend it?
                if desired_order['orderQty'] != order['leavesQty'] or (
                        # If price has changed, and the change is more than our RELIST_INTERVAL, amend.
                        desired_order['price'] != order['price'] and
                        abs((desired_order['price'] / order['price']) - 1) > settings.RELIST_INTERVAL):
                    to_amend.append(
                        {'orderID': order['orderID'], 'orderQty': order['cumQty'] + desired_order['orderQty'],
                         'price': desired_order['price'], 'side': order['side']})
            except IndexError:
                # Will throw if there isn't a desired order to match. In that case, cancel it.
                to_cancel.append(order)

        while buys_matched < len(buy_orders):
            to_create.append(buy_orders[buys_matched])
            buys_matched += 1

        while sells_matched < len(sell_orders):
            to_create.append(sell_orders[sells_matched])
            sells_matched += 1

        if len(to_amend) > 0:
            for amended_order in reversed(to_amend):
                reference_order = [o for o in existing_orders if o['orderID'] == amended_order['orderID']][0]
                self.logger.info("Amending %4s: %d @ %.*f to %d @ %.*f (%+.*f)" % (
                    amended_order['side'],
                    reference_order['leavesQty'], tickLog, reference_order['price'],
                    (amended_order['orderQty'] - reference_order['cumQty']), tickLog, amended_order['price'],
                    tickLog, (amended_order['price'] - reference_order['price'])
                ))
            # This can fail if an order has closed in the time we were processing.
            # The API will send us `invalid ordStatus`, which means that the order's status (Filled/Canceled)
            # made it not amendable.
            # If that happens, we need to catch it and re-tick.
            try:
                self.exchange.amend_bulk_orders(to_amend)
            except requests.exceptions.HTTPError as e:
                errorObj = e.response.json()
                if errorObj['error']['message'] == 'Invalid ordStatus':
                    self.logger.warn("Amending failed. Waiting for order data to converge and retrying.")
                    sleep(0.5)
                    return self.place_orders()
                else:
                    self.logger.error("Unknown error on amend: %s. Exiting" % errorObj)
                    sys.exit(1)

        if len(to_create) > 0:
            self.logger.info("Creating %d orders:" % (len(to_create)))
            for order in reversed(to_create):
                self.logger.info("%4s %d @ %.*f" % (order['side'], order['orderQty'], tickLog, order['price']))
            self.exchange.create_bulk_orders(to_create)

        # Could happen if we exceed a delta limit
        if len(to_cancel) > 0:
            self.logger.info("Canceling %d orders:" % (len(to_cancel)))
            for order in reversed(to_cancel):
                self.logger.info("%4s %d @ %.*f" % (order['side'], order['leavesQty'], tickLog, order['price']))
            self.exchange.cancel_bulk_orders(to_cancel)

    ###
    # Position Limits
    ###

    def short_position_limit_exceeded(self):
        """Returns True if the short position limit is exceeded"""
        if not settings.CHECK_POSITION_LIMITS:
            return False
        position = self.exchange.get_delta()
        return position <= settings.MIN_POSITION

    def long_position_limit_exceeded(self):
        """Returns True if the long position limit is exceeded"""
        if not settings.CHECK_POSITION_LIMITS:
            return False
        position = self.exchange.get_delta()
        return position >= settings.MAX_POSITION

    ###
    # Sanity
    ##

    def sanity_check(self):
        """Perform checks before placing orders."""

        # Check if OB is empty - if so, can't quote.
        self.exchange.check_if_orderbook_empty()

        # Ensure market is still open.
        self.exchange.check_market_open()

        # Get ticker, which sets price offsets and prints some debugging info.
        ticker = self.get_ticker()

        # Sanity check:
        if self.get_price_offset(-1) >= ticker["sell"] or self.get_price_offset(1) <= ticker["buy"]:
            self.logger.error("Buy: %s, Sell: %s" % (self.start_position_buy, self.start_position_sell))
            self.logger.error(
                "First buy position: %s\nBitMEX Best Ask: %s\nFirst sell position: %s\nBitMEX Best Bid: %s" %
                (self.get_price_offset(-1), ticker["sell"], self.get_price_offset(1), ticker["buy"]))
            self.logger.error("Sanity check failed, exchange data is inconsistent")
            self.exit()

        # Messaging if the position limits are reached
        if self.long_position_limit_exceeded():
            self.logger.info("Long delta limit exceeded")
            self.logger.info("Current Position: %.f, Maximum Position: %.f" %
                             (self.exchange.get_delta(), settings.MAX_POSITION))

        if self.short_position_limit_exceeded():
            self.logger.info("Short delta limit exceeded")
            self.logger.info("Current Position: %.f, Minimum Position: %.f" %
                             (self.exchange.get_delta(), settings.MIN_POSITION))

    ###
    # Running
    ###

    def check_file_change(self):
        """Restart if any files we're watching have changed."""
        pass
        # for f, mtime in watched_files_mtimes:
        #     if getmtime(f) > mtime:
        #         self.restart()

    def check_connection(self):
        """Ensure the WS connections are still open."""
        return self.exchange.is_open()

    def exit(self):
        self.logger.info("Shutting down. All open orders will be cancelled.")
        try:
            self.exchange.cancel_all_orders()
            self.exchange.bitmex.exit()
        except errors.AuthenticationError as e:
            self.logger.info("Was not authenticated; could not cancel orders.")
        except Exception as e:
            self.logger.info("Unable to cancel orders: %s" % e)

        sys.exit()

    def run_loop(self):
        while True:
            sys.stdout.write("-----\n")
            sys.stdout.flush()

            # self.check_file_change()
            sleep(settings.LOOP_INTERVAL)

            # This will restart on very short downtime, but if it's longer,
            # the MM will crash entirely as it is unable to connect to the WS on boot.
            if not self.check_connection():
                self.logger.error("Realtime data connection unexpectedly closed, restarting.")
                self.restart()

            self.sanity_check()  # Ensures health of mm - several cut-out points here
            self.print_status()  # Print skew, delta, etc
            self.place_orders()  # Creates desired orders and converges to existing orders

    def restart(self):
        self.logger.info("Restarting the market maker...")
        os.execv(sys.executable, [sys.executable] + sys.argv)


#
# Helpers
#


def XBt_to_XBT(XBt):
    return float(XBt) / constants.XBt_TO_XBT


def cost(instrument, quantity, price):
    mult = instrument["multiplier"]
    P = mult * price if mult >= 0 else mult / price
    return abs(quantity * P)


def margin(instrument, quantity, price):
    return cost(instrument, quantity, price) * instrument["initMargin"]


def run():
    # self.logger.info('BitMEX Market Maker Version: %s\n' % constants.VERSION)

    om = OrderManager()
    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        om.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
