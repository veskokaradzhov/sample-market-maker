import sys
import pandas as pd

from market_maker.market_maker import OrderManager


class CustomOrderManager(OrderManager):
    """A sample order manager for implementing your own custom strategy"""

    def place_orders(self) -> None:
        # implement your custom strategy here

        buy_orders = []
        sell_orders = []

        # populate buy and sell orders, e.g.
        # buy_orders.append({'price': 999.0, 'orderQty': 100, 'side': "Buy"})
        # sell_orders.append({'price': 1001.0, 'orderQty': 100, 'side': "Sell"})

        orderbook = pd.DataFrame(self.exchange.bitmex.market_depth())
        orderbook = orderbook.sort_values('price', ascending=False).reset_index(drop=True)
        edge_buy = orderbook[orderbook['side'] == 'Buy'].iloc[2:]['size'].idxmax() - 1
        edge_sell = orderbook[orderbook['side'] == 'Sell'].iloc[:-2]['size'].idxmax() + 1
        if not self.long_position_limit_exceeded():
            buy_orders.append({'price': orderbook.iloc[edge_buy]['price'], 'orderQty': 100, 'side': "Buy"})
        if not self.short_position_limit_exceeded():
            sell_orders.append({'price': orderbook.iloc[edge_sell]['price'], 'orderQty': 100, 'side': "Sell"})
        self.converge_orders(buy_orders, sell_orders)


def run() -> None:
    order_manager = CustomOrderManager()

    # Try/except just keeps ctrl-c from printing an ugly stacktrace
    try:
        order_manager.run_loop()
    except (KeyboardInterrupt, SystemExit):
        sys.exit()
