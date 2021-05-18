import atexit
# Used for reloading the bot - saves modified times of key files
import os
import random
import signal
import sys
from datetime import datetime
from time import sleep
from collections import deque
import numpy as np
import requests
from matplotlib import pyplot as plt
from market_maker.exchange_interface import ExchangeInterface
from market_maker.settings_util import settings
from market_maker.utils import log, constants, errors, math
from market_maker.utils.trades_functions import estimate_trade_arrival_intensity, get_empirical_trade_size_cdfs
from market_maker.utils.market_impact import buy_mo_market_impact_function, sell_mo_market_impact_function
from market_maker.utils.market_impact import buy_mo_inverse_market_impact, sell_mo_inverse_market_impact, get_mid, \
    get_tob_prices

TRADES_DEQUE_SIZE = 200  # number of trades to obtain statistical estimates of the arrival intensity and size CDF
PRICE_GRANULARITY = 0.5
MO_PREVENTION_DEPTH = 2 * PRICE_GRANULARITY


def find_trade(list_of_trade_dicts, match_id):
    # 'trdMatchID': '512cf496-502b-882d-2c75-ef81a5b1b6d4'
    for trade in list_of_trade_dicts:
        if trade['trdMatchID'] == match_id:
            return True
    return False


def get_set_of_trade_ids_from_deque(trades_deque: deque) -> set:
    ids = set()
    for trade in trades_deque:
        ids.add(trade['trdMatchID'])
    return ids


def rho(x, cdf_func):
    """ x is the quantity of the incoming MO """
    return cdf_func(x)


def apply_inventory_markup(optimal_bid, optimal_ask, current_position, best_bid, best_ask):
    """ Return (markup_bid, markup_ask

    if large positive inventory, widen bid level, shrink ask level
    """

    minus_threshold = -settings.ORDER_START_SIZE
    plus_threshold = settings.ORDER_START_SIZE
    long_level_1 = plus_threshold + 2 * settings.ORDER_STEP_SIZE
    long_level_2 = long_level_1 + 2 * settings.ORDER_STEP_SIZE
    long_level_3 = long_level_2 + 2 * settings.ORDER_STEP_SIZE
    short_level_1 = minus_threshold - 2 * settings.ORDER_STEP_SIZE
    short_level_2 = short_level_1 - 2 * settings.ORDER_STEP_SIZE
    short_level_3 = short_level_2 - 2 * settings.ORDER_STEP_SIZE

    if minus_threshold <= current_position <= plus_threshold:  # within thresholds, small position
        return optimal_bid, optimal_ask
    # longs
    elif plus_threshold < current_position <= long_level_1:
        return optimal_bid - 1 * PRICE_GRANULARITY, optimal_ask
    elif long_level_1 < current_position <= long_level_2:
        return optimal_bid - 2 * PRICE_GRANULARITY, optimal_ask
    elif long_level_2 < current_position <= long_level_3:
        return optimal_bid - 3 * PRICE_GRANULARITY, max(optimal_ask - PRICE_GRANULARITY, best_ask)
    elif current_position > long_level_3:
        return optimal_bid - 4 * PRICE_GRANULARITY, max(optimal_ask - 2 * PRICE_GRANULARITY, best_ask)

    # shorts
    elif minus_threshold > current_position >= short_level_1:
        return optimal_bid, optimal_ask + 1 * PRICE_GRANULARITY
    elif short_level_1 > current_position >= short_level_2:
        return optimal_bid, optimal_ask + 2 * PRICE_GRANULARITY
    elif short_level_2 > current_position >= short_level_3:
        return min(optimal_bid + PRICE_GRANULARITY, best_bid), optimal_ask + 3 * PRICE_GRANULARITY
    elif current_position < short_level_3:
        return min(optimal_bid + 2 * PRICE_GRANULARITY, best_bid), optimal_ask + 4 * PRICE_GRANULARITY
    else:
        raise ValueError('can not happen')


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
        self.trades_deque = deque(maxlen=TRADES_DEQUE_SIZE)
        self.stored_trade_ids = set()
        self.loop_counter = 1
        self.context = dict()
        self.optimal_buy_lo_level = None
        self.optimal_sell_lo_level = None
        self.reset()

    def reset(self):
        self.exchange.cancel_all_orders()
        self.sanity_check()
        self.update_state()

        # Create orders and converge.
        # self.place_orders()

    def update_state(self):
        """Update the current MM state"""

        margin = self.exchange.get_margin()
        position = self.exchange.get_position()
        self.running_qty = self.exchange.get_delta()
        tickLog = self.exchange.get_instrument()['tickLog']
        self.start_XBt = margin["marginBalance"]

        order_book = self.exchange.bitmex.market_depth()
        self.logger.info('Order Book: {}'.format(order_book))

        self.stored_trade_ids = get_set_of_trade_ids_from_deque(self.trades_deque)

        trades = self.exchange.recent_trades()

        for trade in trades:
            if trade['trdMatchID'] not in self.stored_trade_ids:
                self.trades_deque.append(trade)
        # keep this set updated
        self.stored_trade_ids = get_set_of_trade_ids_from_deque(self.trades_deque)

        # self.logger.info('Recent Trades: {}'.format(trades))
        self.logger.info('Number of Trades: {}'.format(len(self.trades_deque)))
        # self.logger.info('Trades Deque: {}'.format(self.trades_deque))
        #
        # lambda_buy_arrivals, lambda_sell_arrivals = estimate_trade_arrival_intensity(self.trades_deque, self.logger,
        #                                                                              verbose=True)

        sell_quantities = [trade['size'] for trade in self.trades_deque if trade['side'] == 'Sell']
        buy_quantities = [trade['size'] for trade in self.trades_deque if trade['side'] == 'Buy']

        if len(sell_quantities) > 10 and len(buy_quantities) > 10 and len(self.trades_deque) > 20:
            buy_cdf, sell_cdf = get_empirical_trade_size_cdfs(list(self.trades_deque))

            incoming_buy_mo_sizes = [1] + [x for x in range(0, max(buy_quantities) + 1, 5) if x > 0]
            incoming_sell_mo_sizes = [1] + [x for x in range(0, max(sell_quantities) + 1, 5) if x > 0]

            buy_market_impacts = np.array(
                [buy_mo_market_impact_function(order_book, x) for x in incoming_buy_mo_sizes])
            sell_market_impacts = np.array(
                [sell_mo_market_impact_function(order_book, x) for x in incoming_sell_mo_sizes])
            mid_price = get_mid(order_book)
            best_bid, best_ask = get_tob_prices(order_book)
            half_spread = best_ask - mid_price

            max_buy_impact = max(buy_market_impacts)
            max_sell_impact = max(sell_market_impacts)

            sell_lo_depths = [half_spread] + [x for x in np.linspace(PRICE_GRANULARITY, max_buy_impact,
                                                                     2 * int(max_buy_impact) + 1, endpoint=True)]
            buy_lo_depths = [half_spread] + [x for x in np.linspace(PRICE_GRANULARITY, max_sell_impact,
                                                                    2 * int(max_buy_impact) + 1, endpoint=True)]

            # sell_lo_depths = [x for x in np.linspace(0.0, 30, 61)]
            # buy_lo_depths = [x for x in np.linspace(0.0, 30, 61)]
            posted_depths = []
            fill_probs = []
            #
            for posted_depth in sell_lo_depths:
                critical_mo_size = buy_mo_inverse_market_impact(order_book, posted_depth)
                prob_filled = 1 - rho(critical_mo_size, buy_cdf)
                # print(posted_depth, critical_mo_size, prob_filled)
                posted_depths.append(posted_depth)
                fill_probs.append(prob_filled)

            value_function = np.array(posted_depths) * np.array(fill_probs)
            max_val_index_sell_lo = np.nanargmax(value_function)

            optimal_sell_lo_depth = math.to_nearest(posted_depths[max_val_index_sell_lo], PRICE_GRANULARITY)
            optimal_sell_lo_post = math.to_nearest(mid_price + optimal_sell_lo_depth + MO_PREVENTION_DEPTH,
                                                   PRICE_GRANULARITY)

            posted_depths = []
            fill_probs = []
            #
            for posted_depth in buy_lo_depths:
                critical_mo_size = sell_mo_inverse_market_impact(order_book, posted_depth)
                prob_filled = 1 - rho(critical_mo_size, sell_cdf)
                # print(posted_depth, critical_mo_size, prob_filled)
                posted_depths.append(posted_depth)
                fill_probs.append(prob_filled)

            value_function = np.array(posted_depths) * np.array(fill_probs)
            max_val_index_buy_lo = np.nanargmax(value_function)

            optimal_buy_lo_depth = math.to_nearest(posted_depths[max_val_index_buy_lo], PRICE_GRANULARITY)
            optimal_buy_lo_post = math.to_nearest(mid_price - optimal_buy_lo_depth - MO_PREVENTION_DEPTH,
                                                  PRICE_GRANULARITY)

            optimal_buy_lo_post, optimal_sell_lo_post = apply_inventory_markup(optimal_buy_lo_post, optimal_sell_lo_post, position, best_bid, best_ask)

            self.logger.info("optimal_buy_lo_post: {}".format(optimal_buy_lo_post))
            self.logger.info("optimal_sell_lo_post: {}".format(optimal_sell_lo_post))
            self.optimal_buy_lo_level = optimal_buy_lo_post
            self.optimal_sell_lo_level = optimal_sell_lo_post
            self.context['optimal_buy_lo_level'] = optimal_buy_lo_post
            self.context['optimal_sell_lo_level'] = optimal_sell_lo_post

            # self.logger.info("Current Contract Position: %d" % self.running_qty)
            # plt.figure()
            # plt.plot(posted_depths, value_function, c='r')
            # plt.xlabel('LO depth')
            # plt.ylabel('Expected Profit Per Trade')
            # plt.title('Expected Profit per Trade (sell MO)')
            # plt.savefig('value_sell_mo_{}.png'.format(self.loop_counter))

            self.loop_counter += 1

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

        raise NotImplementedError

        # buy_orders = []
        # sell_orders = []
        # # Create orders from the outside in. This is intentional - let's say the inner order gets taken;
        # # then we match orders from the outside in, ensuring the fewest number of orders are amended and only
        # # a new order is created in the inside. If we did it inside-out, all orders would be amended
        # # down and a new order would be created at the outside.
        # for i in reversed(range(1, settings.ORDER_PAIRS + 1)):
        #     if not self.long_position_limit_exceeded():
        #         buy_orders.append(self.prepare_order(-i))
        #     if not self.short_position_limit_exceeded():
        #         sell_orders.append(self.prepare_order(i))
        #
        # return self.converge_orders(buy_orders, sell_orders)

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

        trades_response = requests.get('https://testnet.bitmex.com/api/v1/trade?symbol=XBT&count=100&reverse=false')
        # trades_response = requests.get('https://bitmex.com/api/v1/trade?symbol=XBT&count=100&reverse=false')
        initial_trades = trades_response.json()
        # print(type(initial_trades))
        for trade in initial_trades:
            self.trades_deque.append(trade)

        while True:
            sys.stdout.write("-----\n")
            sys.stdout.flush()

            # self.check_file_change()
            # sleep(settings.LOOP_INTERVAL)

            # This will restart on very short downtime, but if it's longer,
            # the MM will crash entirely as it is unable to connect to the WS on boot.
            if not self.check_connection():
                self.logger.error("Realtime data connection unexpectedly closed, restarting.")
                self.restart()

            self.sanity_check()  # Ensures health of mm - several cut-out points here
            self.update_state()  # Print skew, delta, etc
            self.place_orders()  # Creates desired orders and converges to existing orders

    def restart(self):
        self.logger.info("Restarting the market maker...")
        os.execv(sys.executable, [sys.executable] + sys.argv)


def XBt_to_XBT(XBt):
    return float(XBt) / constants.XBt_TO_XBT


def cost(instrument, quantity, price):
    mult = instrument["multiplier"]
    P = mult * price if mult >= 0 else mult / price
    return abs(quantity * P)


def margin(instrument, quantity, price):
    return cost(instrument, quantity, price) * instrument["initMargin"]
