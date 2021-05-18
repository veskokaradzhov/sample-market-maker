import sys
import pandas as pd
from market_maker.rx_helper import pipe_wrap
from rx.subject import Subject
import settings

from market_maker.order_manager import OrderManager


def fetch_edge_price(orderbook: pd.DataFrame):
    orderbook.loc[:, 'ratio'] = orderbook['size'] / orderbook['size'].cumsum()
    orderbook = orderbook.reset_index(drop=True)
    edge_idx = orderbook.iloc[1:]['ratio'].idxmax() - 1
    return orderbook.loc[edge_idx]['price']


def process_orders(context, enabler, side, size, tag):
    if not context[enabler]:
        orders = []
        orderbook = context['orderbook']
        book: pd.DataFrame = orderbook[orderbook['side'] == side]
        if side == 'Sell':
            book.sort_index(ascending=False, inplace=True)
        price = fetch_edge_price(book)
        orders.append({'price': price, 'orderQty': size, 'side': side})
        context[tag] = orders
    return context


@pipe_wrap
def process_buy_orders(context):
    return process_orders(context, 'long_limit_reached', 'Buy', settings.ORDER_STEP_SIZE, 'buy_orders')


@pipe_wrap
def process_sell_orders(context):
    return process_orders(context, 'short_limit_reached', 'Sell', settings.ORDER_STEP_SIZE, 'sell_orders')


@pipe_wrap
def check_position_limits(context):
    if settings.CHECK_POSITION_LIMITS:
        position = context['exchange'].get_delta()
        context['short_limit_reached'] = position <= settings.MIN_POSITION
        context['long_limit_reached'] = position >= settings.MAX_POSITION
    else:
        context['short_limit_reached'] = False
        context['long_limit_reached'] = False
    return context


class CustomOrderManager(OrderManager):
    """A sample order manager for implementing your own custom strategy"""
    def __init__(self):
        super().__init__()
        self.context = {'exchange': self.exchange}
        self.orderbook_stream = Subject()
        self.orderbook_stream.pipe(
            check_position_limits(),
            process_buy_orders(),
            process_sell_orders()
        ).subscribe(self.flush_orders)

    def flush_orders(self, context):
        buy_orders = context['buy_orders'] if 'buy_orders' in context else []
        sell_orders = context['sell_orders'] if 'sell_orders' in context else []
        self.converge_orders(buy_orders, sell_orders)

    def place_orders(self):
        orderbook = pd.DataFrame(self.exchange.bitmex.market_depth())
        orderbook = orderbook.sort_values('price', ascending=False).reset_index(drop=True)
        self.context['orderbook'] = orderbook
        self.orderbook_stream.on_next(self.context)


def run() -> None:
    order_manager = CustomOrderManager()

    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        order_manager.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
