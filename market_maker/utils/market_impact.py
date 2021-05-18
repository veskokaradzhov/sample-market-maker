import sys
from typing import Dict, List, Tuple, Union
import numpy as np
from matplotlib import pyplot as plt

FLOAT_INFINITY = float('inf')


def get_ask_side(book: List[Dict]) -> List[Dict]:
    """
    Get the ask side of the order book, sorted by price in increasing order (i.e. moving away from the best offer)
    """
    levels = []
    for level in book:
        if level['side'] == 'Sell':
            levels.append(level)
    return sorted(levels, key=lambda k: k['price'], reverse=False)


def get_bid_side(book: List[Dict]) -> List[Dict]:
    """
    Get the bid side of the order book, sorted by price in decreasing order (i.e. moving away from best bid)
    """
    levels = []
    for level in book:
        if level['side'] == 'Buy':
            levels.append(level)
    return sorted(levels, key=lambda k: k['price'], reverse=True)


def get_tob(book: List[Dict]) -> Tuple[Union[Dict, None], Union[Dict, None]]:
    """
    Gets the best bid and best ask levels (dictionaries including price and quantity) given an order book.
    """
    bids = get_bid_side(book)
    asks = get_ask_side(book)

    if not bids:
        best_bid = None
    else:
        best_bid = bids[0]
    if not asks:
        best_ask = None
    else:
        best_ask = asks[0]

    return best_bid, best_ask


def get_mid(book):
    b, a = get_tob(book)
    if b is None and a is not None:
        return a['price']
    if a is None and b is not None:
        return b['price']
    if a is None and b is None:
        return None

    mid = 0.5 * (a['price'] + b['price'])
    return mid


def compute_cumulative_qty(book_side):
    qtys = []
    cqty = 0
    for level in book_side:
        cqty += level['size']
        qtys.append(cqty)
    return qtys


def get_tob_prices(book):
    b, a = get_tob(book)
    if b is None and a is not None:
        return None, a['price']
    if b is not None and a is None:
        return b['price'], None
    if b is None and a is None:
        return None, None
    return b['price'], a['price']


def sell_mo_market_impact_function(book, mo_quantity):
    """
    Compute the impact of incoming sell MO on the price
    """
    if mo_quantity < 0:
        raise ValueError('market order quantity cannot be < 0')
    if mo_quantity == 0:
        return 0.0
    mid = get_mid(book)
    if mid is None:
        return None

    bid_side_of_book = get_bid_side(book)
    if not bid_side_of_book:
        return None
    cumulative_qtys = compute_cumulative_qty(bid_side_of_book)

    cqtys = [0.0] + cumulative_qtys + [FLOAT_INFINITY]
    bid_levels = len(bid_side_of_book)

    if mo_quantity == 0:
        return mid - bid_side_of_book[0]['price']

    for i, (first, second) in enumerate(zip(cqtys, cqtys[1:])):
        if (mo_quantity > first) and (mo_quantity <= second):
            if i <= bid_levels - 1:
                return mid - bid_side_of_book[i]['price']
            else:
                return mid - bid_side_of_book[-1]['price']


def buy_mo_market_impact_function(book, mo_quantity):
    """
    Compute the impact of incoming sell MO on the price
    """
    if mo_quantity < 0:
        raise ValueError('market order quantity cannot be < 0')
    if mo_quantity == 0:
        return 0.0
    mid = get_mid(book)
    if mid is None:
        return None
    ask_side_of_book = get_ask_side(book)
    if not ask_side_of_book:
        return None
    cumulative_qtys = compute_cumulative_qty(ask_side_of_book)

    cqtys = [0.0] + cumulative_qtys + [FLOAT_INFINITY]
    ask_levels = len(ask_side_of_book)

    if mo_quantity == 0:
        return ask_side_of_book[0]['price'] - mid

    for i, (first, second) in enumerate(zip(cqtys, cqtys[1:])):
        if (mo_quantity > first) and (mo_quantity <= second):
            if i <= ask_levels - 1:
                return - mid + ask_side_of_book[i]['price']
            else:
                return - mid + ask_side_of_book[-1]['price']


def buy_mo_inverse_market_impact(book, impact):
    """ get the minimum market order quantity that causes a given impact """
    if len(book) == 0:
        return FLOAT_INFINITY
    if impact < 0:
        raise ValueError('market impact cannot be negative')
    best_bid, best_ask = get_tob_prices(book)
    half_spread = (best_ask - best_bid) / 2
    ask_side_of_book = get_ask_side(book)
    if len(ask_side_of_book) == 0:
        return FLOAT_INFINITY
    cumulative_qtys = compute_cumulative_qty(ask_side_of_book)

    cqtys = cumulative_qtys  # + [FLOAT_INFINITY]
    impacts = [buy_mo_market_impact_function(book, cqty) for cqty in cqtys]

    if impact < half_spread:
        return 0
    if impact > max(impacts):
        return FLOAT_INFINITY
    impacts += [FLOAT_INFINITY]
    for i, (first, second) in enumerate(zip(impacts, impacts[1:])):
        if (impact >= first) and (impact < second):
            return cqtys[i]

def sell_mo_inverse_market_impact(book, impact):
    """ get the minimum market order quantity that causes a given impact """
    if len(book) == 0:
        return FLOAT_INFINITY
    if impact < 0:
        raise ValueError('market impact cannot be negative')
    best_bid, best_ask = get_tob_prices(book)
    half_spread = (best_ask - best_bid) / 2
    bid_side_of_book = get_bid_side(book)
    if len(bid_side_of_book) == 0:
        return FLOAT_INFINITY
    cumulative_qtys = compute_cumulative_qty(bid_side_of_book)

    cqtys = cumulative_qtys  # + [FLOAT_INFINITY]
    impacts = [sell_mo_market_impact_function(book, cqty) for cqty in cqtys]

    if impact < half_spread:
        return 0
    if impact > max(impacts):
        return FLOAT_INFINITY
    impacts += [FLOAT_INFINITY]
    for i, (first, second) in enumerate(zip(impacts, impacts[1:])):
        if (impact >= first) and (impact < second):
            return cqtys[i]

#
# def inv_impact(qtys, impacts, d):
#     loc = np.argwhere((impacts >= d))[0][0]
#     # print(qtys[loc])
#     return qtys[loc]


EXAMPLE_ORDER_BOOK = [{'symbol': 'XBTUSD', 'id': 8795076600, 'side': 'Sell', 'size': 3011, 'price': 49234},
                      {'symbol': 'XBTUSD', 'id': 8795076800, 'side': 'Sell', 'size': 98, 'price': 49232},
                      {'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 2073, 'price': 49230.5},
                      {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Sell', 'size': 3652, 'price': 49229},
                      {'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Sell', 'size': 400, 'price': 49228.5},
                      {'symbol': 'XBTUSD', 'id': 8795077200, 'side': 'Sell', 'size': 4000, 'price': 49228},
                      {'symbol': 'XBTUSD', 'id': 8795077250, 'side': 'Sell', 'size': 61456, 'price': 49227.5},
                      {'symbol': 'XBTUSD', 'id': 8795077500, 'side': 'Sell', 'size': 579459, 'price': 49225},
                      {'symbol': 'XBTUSD', 'id': 8795077600, 'side': 'Sell', 'size': 38, 'price': 49224},
                      {'symbol': 'XBTUSD', 'id': 8795077700, 'side': 'Sell', 'size': 334, 'price': 49223},
                      {'symbol': 'XBTUSD', 'id': 8795078100, 'side': 'Sell', 'size': 4, 'price': 49219},
                      {'symbol': 'XBTUSD', 'id': 8795078350, 'side': 'Sell', 'size': 553, 'price': 49216.5},
                      {'symbol': 'XBTUSD', 'id': 8795078400, 'side': 'Sell', 'size': 103, 'price': 49216},
                      {'symbol': 'XBTUSD', 'id': 8795078450, 'side': 'Sell', 'size': 10, 'price': 49215.5},
                      {'symbol': 'XBTUSD', 'id': 8795078750, 'side': 'Sell', 'size': 3000, 'price': 49212.5},
                      {'symbol': 'XBTUSD', 'id': 8795078800, 'side': 'Sell', 'size': 2000, 'price': 49212},
                      {'symbol': 'XBTUSD', 'id': 8795078900, 'side': 'Sell', 'size': 500, 'price': 49211},
                      {'symbol': 'XBTUSD', 'id': 8795078950, 'side': 'Sell', 'size': 1215, 'price': 49210.5},
                      {'symbol': 'XBTUSD', 'id': 8795079000, 'side': 'Sell', 'size': 408, 'price': 49210},
                      {'symbol': 'XBTUSD', 'id': 8795079050, 'side': 'Sell', 'size': 200, 'price': 49209.5},
                      {'symbol': 'XBTUSD', 'id': 8795079250, 'side': 'Sell', 'size': 10, 'price': 49207.5},
                      {'symbol': 'XBTUSD', 'id': 8795079300, 'side': 'Sell', 'size': 200, 'price': 49207},
                      {'symbol': 'XBTUSD', 'id': 8795079750, 'side': 'Sell', 'size': 49, 'price': 49202.5},
                      {'symbol': 'XBTUSD', 'id': 8795079900, 'side': 'Sell', 'size': 58, 'price': 49201},
                      {'symbol': 'XBTUSD', 'id': 8795079950, 'side': 'Sell', 'size': 184143, 'price': 49200.5},
                      {'symbol': 'XBTUSD', 'id': 8795080000, 'side': 'Buy', 'size': 2761523, 'price': 49200},
                      {'symbol': 'XBTUSD', 'id': 8795080150, 'side': 'Buy', 'size': 290443, 'price': 49198.5},
                      {'symbol': 'XBTUSD', 'id': 8795080200, 'side': 'Buy', 'size': 20119, 'price': 49198},
                      {'symbol': 'XBTUSD', 'id': 8795080450, 'side': 'Buy', 'size': 50030, 'price': 49195.5},
                      {'symbol': 'XBTUSD', 'id': 8795080550, 'side': 'Buy', 'size': 18060, 'price': 49194.5},
                      {'symbol': 'XBTUSD', 'id': 8795081000, 'side': 'Buy', 'size': 5, 'price': 49190},
                      {'symbol': 'XBTUSD', 'id': 8795081050, 'side': 'Buy', 'size': 28125, 'price': 49189.5},
                      {'symbol': 'XBTUSD', 'id': 8795081100, 'side': 'Buy', 'size': 2989, 'price': 49189},
                      {'symbol': 'XBTUSD', 'id': 8795081150, 'side': 'Buy', 'size': 33300, 'price': 49188.5},
                      {'symbol': 'XBTUSD', 'id': 8795081200, 'side': 'Buy', 'size': 9510, 'price': 49188},
                      {'symbol': 'XBTUSD', 'id': 8795081400, 'side': 'Buy', 'size': 30009, 'price': 49186},
                      {'symbol': 'XBTUSD', 'id': 8795081500, 'side': 'Buy', 'size': 105000, 'price': 49185},
                      {'symbol': 'XBTUSD', 'id': 8795081550, 'side': 'Buy', 'size': 401500, 'price': 49184.5},
                      {'symbol': 'XBTUSD', 'id': 8795081600, 'side': 'Buy', 'size': 101, 'price': 49184},
                      {'symbol': 'XBTUSD', 'id': 8795081750, 'side': 'Buy', 'size': 79000, 'price': 49182.5},
                      {'symbol': 'XBTUSD', 'id': 8795081800, 'side': 'Buy', 'size': 49154, 'price': 49182},
                      {'symbol': 'XBTUSD', 'id': 8795081900, 'side': 'Buy', 'size': 25000, 'price': 49181},
                      {'symbol': 'XBTUSD', 'id': 8795082100, 'side': 'Buy', 'size': 75000, 'price': 49179},
                      {'symbol': 'XBTUSD', 'id': 8795082150, 'side': 'Buy', 'size': 75000, 'price': 49178.5},
                      {'symbol': 'XBTUSD', 'id': 8795080800, 'side': 'Buy', 'size': 52650, 'price': 49192},
                      {'symbol': 'XBTUSD', 'id': 8795080900, 'side': 'Buy', 'size': 15730, 'price': 49191},
                      {'symbol': 'XBTUSD', 'id': 8795082250, 'side': 'Buy', 'size': 1200, 'price': 49177.5},
                      {'symbol': 'XBTUSD', 'id': 8795082300, 'side': 'Buy', 'size': 668444, 'price': 49177},
                      {'symbol': 'XBTUSD', 'id': 8795082350, 'side': 'Buy', 'size': 217853, 'price': 49176.5},
                      {'symbol': 'XBTUSD', 'id': 8795082400, 'side': 'Buy', 'size': 675512, 'price': 49176}]


def plot_order_book(book):
    sell_quantities = [order['size'] for order in book if order['side'] == 'Sell']
    buy_quantities = [order['size'] for order in book if order['side'] == 'Buy']
    sell_prices = [order['price'] for order in book if order['side'] == 'Sell']
    buy_prices = [order['price'] for order in book if order['side'] == 'Buy']

    plt.figure()
    plt.bar(buy_prices, buy_quantities, width=0.5, color='b')
    plt.bar(sell_prices, sell_quantities, width=0.5, color='r')
    plt.show()


# if __name__ == '__main__':
#     plot_order_book(EXAMPLE_ORDER_BOOK)

if __name__ == '__main__':

    from market_maker.utils.trades_functions import LIST_OF_TRADES, rho, get_empirical_trade_size_cdfs

    HALF_SPREAD = get_mid(EXAMPLE_ORDER_BOOK) - get_tob_prices(EXAMPLE_ORDER_BOOK)[0]
    print('HALF_SPREAD', HALF_SPREAD)
    print('get_tob_prices', get_tob_prices(EXAMPLE_ORDER_BOOK))

    print(buy_mo_market_impact_function(EXAMPLE_ORDER_BOOK, 1))
    print(sell_mo_market_impact_function(EXAMPLE_ORDER_BOOK, 20000))

    sell_quantities = [trade['size'] for trade in LIST_OF_TRADES if trade['side'] == 'Sell']
    buy_quantities = [trade['size'] for trade in LIST_OF_TRADES if trade['side'] == 'Buy']

    print('min sell_quantities', min(sell_quantities))
    print('max sell_quantities', max(sell_quantities))
    print('min buy_quantities', min(buy_quantities))
    print('max buy_quantities', max(buy_quantities))

    incoming_buy_mo_sizes = [1] + [x for x in range(0, 10000000 + 1, 1000) if x > 0]
    incoming_sell_mo_sizes = [1] + [x for x in range(0, 10000000 + 1, 1000) if x > 0]
    print('done')

    buy_market_impacts = np.array([buy_mo_market_impact_function(EXAMPLE_ORDER_BOOK, x) for x in incoming_buy_mo_sizes])
    sell_market_impacts = np.array(
        [sell_mo_market_impact_function(EXAMPLE_ORDER_BOOK, x) for x in incoming_sell_mo_sizes])

    # print(buy_market_impacts)
    # plt.figure()
    # plt.plot(incoming_buy_mo_sizes, buy_market_impacts)
    #
    # plt.figure()
    # plt.plot(incoming_sell_mo_sizes, sell_market_impacts)

    max_buy_impact = max(buy_market_impacts)
    max_sell_impact = max(sell_market_impacts)

    mid_price = get_mid(EXAMPLE_ORDER_BOOK)
    best_bid, best_ask = get_tob_prices(EXAMPLE_ORDER_BOOK)
    half_spread = best_ask - mid_price

    price_granularity = 0.5

    sell_lo_depths = [half_spread] + [x for x in np.linspace(price_granularity, max_buy_impact, 2*int(max_buy_impact) + 1, endpoint=True)]
    buy_lo_depths = [half_spread] + [x for x in np.linspace(price_granularity, max_sell_impact, 2*int(max_buy_impact) + 1, endpoint=True)]


    # sell_lo_depths = [x for x in np.linspace(half_spread, max_buy_impact, 2*int(max_buy_impact) + 1, endpoint=True)]
    # buy_lo_depths = [x for x in np.linspace(half_spread, max_sell_impact + 1.0, 2 * int(max_buy_impact + 0.0))]
    buy_cdf, sell_cdf = get_empirical_trade_size_cdfs(LIST_OF_TRADES)

    #
    posted_depths = []
    fill_probs = []

    print('Sell LOs fill probability given incoming buy MO:')
    for posted_depth in sell_lo_depths:
        critical_mo_size = buy_mo_inverse_market_impact(EXAMPLE_ORDER_BOOK, posted_depth)
        prob_filled = 1 - rho(critical_mo_size, buy_cdf)
        print(posted_depth, critical_mo_size, prob_filled)
        posted_depths.append(posted_depth)
        fill_probs.append(prob_filled)

    value_function = np.array(posted_depths) * np.array(fill_probs)

    plt.figure()
    plt.plot(posted_depths, value_function, c='r')
    plt.xlabel('LO depth')
    plt.ylabel('Expected Profit Per Trade')
    plt.title('Expected Profit per Trade (buy MO, sell LO filled)')
    plt.show()

    # posted_depths = []
    # fill_probs = []

    # print('Buy LOs fill probability given incoming sell MO:')
    # for posted_depth in sell_lo_depths:
    #     critical_mo_size = buy_mo_inverse_market_impact(EXAMPLE_ORDER_BOOK, posted_depth)
    #     prob_filled = 1 - rho(critical_mo_size, buy_cdf)
    #     print(posted_depth, critical_mo_size, prob_filled)
    #     posted_depths.append(posted_depth)
    #     fill_probs.append(prob_filled)


    sys.exit(0)


    # plt.show()

    # print(np.where((buy_market_impacts >= 10.0) & (buy_market_impacts < 10.5)))
    # print(np.where((buy_market_impacts >= 10.0)))

    # def inv_impact(qtys, impacts, d):
    #     loc = np.argwhere((impacts >= d))[0][0]
    #     # print(qtys[loc])
    #     return qtys[loc]

    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 10.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 11.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 12.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 15.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 20.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 30.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 50.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 100.0)

    #

    LO_DEPTHS = [x for x in np.linspace(0.0, 100, 201)]
    LO_DEPTHS = [0.0, 1.0, 2.0]

    #
    posted_depths = []
    fill_probs = []
    #
    for posted_depth in LO_DEPTHS:
        critical_mo_size = buy_mo_inverse_market_impact(EXAMPLE_ORDER_BOOK, posted_depth)
        prob_filled = 1 - rho(critical_mo_size, buy_cdf)
        print(posted_depth, critical_mo_size, prob_filled)
        posted_depths.append(posted_depth)
        fill_probs.append(prob_filled)

    value_function = np.array(posted_depths) * np.array(fill_probs)

    plt.figure()
    plt.plot(posted_depths, value_function, c='b')
    plt.xlabel('LO depth')
    plt.ylabel('Expected Profit Per Trade')
    plt.title('Expected Profit per Trade (buy MO)')
    # plt.show()

    LO_DEPTHS = [x for x in np.linspace(0.0, 200, 401)]

    posted_depths = []
    fill_probs = []
    #
    for posted_depth in LO_DEPTHS:
        critical_mo_size = sell_mo_inverse_market_impact(EXAMPLE_ORDER_BOOK, posted_depth)
        prob_filled = 1 - rho(critical_mo_size, sell_cdf)
        print(posted_depth, critical_mo_size, prob_filled)
        posted_depths.append(posted_depth)
        fill_probs.append(prob_filled)

    value_function = np.array(posted_depths) * np.array(fill_probs)

    plt.figure()
    plt.plot(posted_depths, value_function, c='r')
    plt.xlabel('LO depth')
    plt.ylabel('Expected Profit Per Trade')
    plt.title('Expected Profit per Trade (sell MO)')
    plt.show()

    #################

    # plt.figure()
    # # plt.plot(np.log(incoming_buy_mo_sizes), buy_market_impacts, c='b')
    # plt.plot(incoming_buy_mo_sizes, buy_market_impacts, c='b')
    # plt.xlabel('Buy MO Qty')
    # plt.ylabel('Price impact')
    # plt.ylim((0, max(buy_market_impacts) + min(buy_market_impacts)))

    # plt.figure()
    # plt.plot(incoming_sell_mo_sizes, sell_market_impacts, c='r')
    # # plt.plot(np.log(incoming_sell_mo_sizes), sell_market_impacts, c='r')
    # plt.xlabel('Sell MO Qty')
    # plt.ylabel('Price impact')
    # plt.ylim((0, max(sell_market_impacts) + min(sell_market_impacts)))
    #
    # plt.show()
