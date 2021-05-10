import numpy as np
from matplotlib import pyplot as plt


def get_ask_side(book):
    levels = []
    for level in book:
        if level['side'] == 'Sell':
            levels.append(level)
    return sorted(levels, key=lambda k: k['price'], reverse=False)


def get_bid_side(book):
    levels = []
    for level in book:
        if level['side'] == 'Buy':
            levels.append(level)
    return sorted(levels, key=lambda k: k['price'], reverse=True)


def get_tob(book):
    asks = get_ask_side(book)
    bids = get_bid_side(book)
    return bids[0], asks[0]


def get_mid(book):
    b, a = get_tob(book)
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
    return b['price'], a['price']


def sell_mo_market_impact_function(book, mo_quantity):
    """
    Compute the impact of incoming sell MO on the price
    """
    best_bid, best_ask = get_tob_prices(book)
    mid = get_mid(book)
    bid_side_of_book = get_bid_side(book)
    cumulative_qtys = compute_cumulative_qty(bid_side_of_book)

    cqtys = [0] + cumulative_qtys + [float('inf')]
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
    best_bid, best_ask = get_tob_prices(book)
    mid = get_mid(book)
    ask_side_of_book = get_ask_side(book)
    cumulative_qtys = compute_cumulative_qty(ask_side_of_book)

    cqtys = [0] + cumulative_qtys + [float('inf')]
    ask_levels = len(ask_side_of_book)

    if mo_quantity == 0:
        return ask_side_of_book[0]['price'] - mid

    for i, (first, second) in enumerate(zip(cqtys, cqtys[1:])):
        if (mo_quantity > first) and (mo_quantity <= second):
            if i <= ask_levels - 1:
                return - mid + ask_side_of_book[i]['price']
            else:
                return - mid + ask_side_of_book[-1]['price']


EXAMPLE_ORDER_BOOK = [
    {'symbol': 'XBTUSD', 'id': 15594418600, 'side': 'Sell', 'size': 2000, 'price': 55814},
    {'symbol': 'XBTUSD', 'id': 15594419800, 'side': 'Sell', 'size': 28, 'price': 55802},
    {'symbol': 'XBTUSD', 'id': 15594421100, 'side': 'Sell', 'size': 230, 'price': 55789},
    {'symbol': 'XBTUSD', 'id': 15594421400, 'side': 'Sell', 'size': 1150, 'price': 55786},
    {'symbol': 'XBTUSD', 'id': 15594421500, 'side': 'Sell', 'size': 11771, 'price': 55785},
    {'symbol': 'XBTUSD', 'id': 15594425950, 'side': 'Sell', 'size': 5167, 'price': 55740.5},
    {'symbol': 'XBTUSD', 'id': 15594426600, 'side': 'Sell', 'size': 2000, 'price': 55734},
    {'symbol': 'XBTUSD', 'id': 15594430500, 'side': 'Sell', 'size': 4000, 'price': 55695},
    {'symbol': 'XBTUSD', 'id': 15594432300, 'side': 'Sell', 'size': 47736, 'price': 55677},
    {'symbol': 'XBTUSD', 'id': 15594433000, 'side': 'Sell', 'size': 45, 'price': 55670},
    {'symbol': 'XBTUSD', 'id': 15594433200, 'side': 'Sell', 'size': 918, 'price': 55668},
    {'symbol': 'XBTUSD', 'id': 15594433350, 'side': 'Sell', 'size': 30, 'price': 55666.5},
    {'symbol': 'XBTUSD', 'id': 15594433600, 'side': 'Sell', 'size': 4000, 'price': 55664},
    {'symbol': 'XBTUSD', 'id': 15594434950, 'side': 'Sell', 'size': 12243, 'price': 55650.5},
    {'symbol': 'XBTUSD', 'id': 15594435800, 'side': 'Sell', 'size': 6121, 'price': 55642},
    {'symbol': 'XBTUSD', 'id': 15594436700, 'side': 'Sell', 'size': 4000, 'price': 55633},
    {'symbol': 'XBTUSD', 'id': 15594439150, 'side': 'Sell', 'size': 2000, 'price': 55608.5},
    {'symbol': 'XBTUSD', 'id': 15594439500, 'side': 'Sell', 'size': 865, 'price': 55605},
    {'symbol': 'XBTUSD', 'id': 15594439800, 'side': 'Sell', 'size': 4000, 'price': 55602},
    {'symbol': 'XBTUSD', 'id': 15594439950, 'side': 'Sell', 'size': 1500, 'price': 55600.5},
    {'symbol': 'XBTUSD', 'id': 15594440600, 'side': 'Sell', 'size': 458, 'price': 55594},
    {'symbol': 'XBTUSD', 'id': 15594441100, 'side': 'Sell', 'size': 1604, 'price': 55589},
    {'symbol': 'XBTUSD', 'id': 15594442750, 'side': 'Sell', 'size': 2576, 'price': 55572.5},
    {'symbol': 'XBTUSD', 'id': 15594442900, 'side': 'Sell', 'size': 5544, 'price': 55571},
    {'symbol': 'XBTUSD', 'id': 15594443900, 'side': 'Buy', 'size': 10000, 'price': 55561},
    {'symbol': 'XBTUSD', 'id': 15594444200, 'side': 'Buy', 'size': 2500, 'price': 55558},
    {'symbol': 'XBTUSD', 'id': 15594445050, 'side': 'Buy', 'size': 12243, 'price': 55549.5},
    {'symbol': 'XBTUSD', 'id': 15594445400, 'side': 'Buy', 'size': 440398, 'price': 55546},
    {'symbol': 'XBTUSD', 'id': 15594446000, 'side': 'Buy', 'size': 1599, 'price': 55540},
    {'symbol': 'XBTUSD', 'id': 15594446100, 'side': 'Buy', 'size': 1372, 'price': 55539},
    {'symbol': 'XBTUSD', 'id': 15594448750, 'side': 'Buy', 'size': 687, 'price': 55512.5},
    {'symbol': 'XBTUSD', 'id': 15594450000, 'side': 'Buy', 'size': 513, 'price': 55500},
    {'symbol': 'XBTUSD', 'id': 15594456200, 'side': 'Buy', 'size': 457, 'price': 55438},
    {'symbol': 'XBTUSD', 'id': 15594460350, 'side': 'Buy', 'size': 1039, 'price': 55396.5},
    {'symbol': 'XBTUSD', 'id': 15594460400, 'side': 'Buy', 'size': 1709, 'price': 55396},
    {'symbol': 'XBTUSD', 'id': 15594460600, 'side': 'Buy', 'size': 4000, 'price': 55394},
    {'symbol': 'XBTUSD', 'id': 15594461400, 'side': 'Buy', 'size': 4000, 'price': 55386},
    {'symbol': 'XBTUSD', 'id': 15594461500, 'side': 'Buy', 'size': 1283, 'price': 55385},
    {'symbol': 'XBTUSD', 'id': 15594463650, 'side': 'Buy', 'size': 2000, 'price': 55363.5},
    {'symbol': 'XBTUSD', 'id': 15594464450, 'side': 'Buy', 'size': 4000, 'price': 55355.5},
    {'symbol': 'XBTUSD', 'id': 15594465400, 'side': 'Buy', 'size': 40456, 'price': 55346},
    {'symbol': 'XBTUSD', 'id': 15594467500, 'side': 'Buy', 'size': 4000, 'price': 55325},
    {'symbol': 'XBTUSD', 'id': 15594469000, 'side': 'Buy', 'size': 1146, 'price': 55310},
    {'symbol': 'XBTUSD', 'id': 15594413000, 'side': 'Sell', 'size': 578, 'price': 55870},
    {'symbol': 'XBTUSD', 'id': 15594469800, 'side': 'Buy', 'size': 4000, 'price': 55302},
    {'symbol': 'XBTUSD', 'id': 15594469900, 'side': 'Buy', 'size': 912, 'price': 55301},
    {'symbol': 'XBTUSD', 'id': 15594470400, 'side': 'Buy', 'size': 867775, 'price': 55296},
    {'symbol': 'XBTUSD', 'id': 15594470600, 'side': 'Buy', 'size': 4000, 'price': 55294},
    {'symbol': 'XBTUSD', 'id': 15594471600, 'side': 'Buy', 'size': 1411, 'price': 55284},
    {'symbol': 'XBTUSD', 'id': 15594471800, 'side': 'Buy', 'size': 2736, 'price': 55282}]

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

    incoming_buy_mo_sizes = [1] + [x for x in range(0, max(buy_quantities) + 1, 10) if x > 0]
    incoming_sell_mo_sizes = [1] + [x for x in range(0, max(sell_quantities) + 1, 10) if x > 0]

    buy_market_impacts = np.array([buy_mo_market_impact_function(EXAMPLE_ORDER_BOOK, x) for x in incoming_buy_mo_sizes])
    sell_market_impacts = np.array([sell_mo_market_impact_function(EXAMPLE_ORDER_BOOK, x) for x in incoming_sell_mo_sizes])

    # print(np.where((buy_market_impacts >= 10.0) & (buy_market_impacts < 10.5)))
    # print(np.where((buy_market_impacts >= 10.0)))

    def inv_impact(qtys, impacts, d):
        loc = np.argwhere((impacts >= d))[0][0]
        # print(qtys[loc])
        return qtys[loc]


    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 10.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 11.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 12.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 15.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 20.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 30.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 50.0)
    # inv_impact(incoming_buy_mo_sizes, buy_market_impacts, 100.0)

    #
    buy_cdf, sell_cdf = get_empirical_trade_size_cdfs(LIST_OF_TRADES)

    LO_DEPTHS = [x for x in np.linspace(0.0, 150, 301)]


    #
    posted_depths = []
    fill_probs = []
    #
    for posted_depth in LO_DEPTHS:
        critical_mo_size = inv_impact(incoming_buy_mo_sizes, buy_market_impacts, posted_depth)
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

    LO_DEPTHS = [x for x in np.linspace(0.0, 20, 41)]

    posted_depths = []
    fill_probs = []
    #
    for posted_depth in LO_DEPTHS:
        critical_mo_size = inv_impact(incoming_sell_mo_sizes, sell_market_impacts, posted_depth)
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
