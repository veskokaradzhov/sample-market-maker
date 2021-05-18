from matplotlib import pyplot as plt
from market_maker.utils.market_impact import get_ask_side, get_bid_side, get_mid, get_tob_prices, get_tob
from market_maker.utils.market_impact import compute_cumulative_qty
from market_maker.utils.market_impact import sell_mo_market_impact_function, buy_mo_market_impact_function
from market_maker.utils.market_impact import buy_mo_inverse_market_impact, sell_mo_inverse_market_impact
from market_maker.utils.market_impact import FLOAT_INFINITY

import unittest


class TestOrderBookAndMarketImpactFunctions(unittest.TestCase):

    def test_get_tob(self):
        lob = []
        self.assertEqual((None, None), get_tob(lob))

        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 2073, 'price': 49230.5}]
        self.assertEqual((None, lob[0]), get_tob(lob))

        lob = [{'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Buy', 'size': 400, 'price': 49228.5}]
        self.assertEqual((lob[0], None), get_tob(lob))

    def test_tob_prices(self):
        lob = []
        self.assertEqual((None, None), get_tob_prices(lob))

        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 2073, 'price': 49230.5}]
        self.assertAlmostEqual(49230.5, get_tob_prices(lob)[1])
        self.assertIsNone(get_tob_prices(lob)[0])

        lob = [{'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Buy', 'size': 400, 'price': 49228.5}]
        self.assertAlmostEqual(49228.5, get_tob_prices(lob)[0])
        self.assertIsNone(get_tob_prices(lob)[1])

    def test_get_ask_and_bid_side(self):
        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 2073, 'price': 49230.5},
               {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Sell', 'size': 3652, 'price': 49229},
               {'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Buy', 'size': 400, 'price': 49228.5},
               {'symbol': 'XBTUSD', 'id': 8795077200, 'side': 'Buy', 'size': 4000, 'price': 49228}]

        ask_side = [{'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Sell', 'size': 3652, 'price': 49229},
                    {'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 2073, 'price': 49230.5}]
        bid_side = [{'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Buy', 'size': 400, 'price': 49228.5},
                    {'symbol': 'XBTUSD', 'id': 8795077200, 'side': 'Buy', 'size': 4000, 'price': 49228}]

        self.assertEqual(ask_side, get_ask_side(lob))
        self.assertEqual(bid_side, get_bid_side(lob))

        self.assertAlmostEqual(49228.75, get_mid(lob))
        best_bid, best_ask = get_tob_prices(lob)
        self.assertAlmostEqual(49228.5, best_bid)
        self.assertAlmostEqual(49229, best_ask)

    def test_get_sides_one_sided_lob(self):
        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 25, 'price': 101.0}]
        self.assertEqual(lob, get_ask_side(lob))
        self.assertEqual([], get_bid_side(lob))

        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Buy', 'size': 25, 'price': 101.0}]

        self.assertEqual(lob, get_bid_side(lob))
        self.assertEqual([], get_ask_side(lob))

        lob = []
        self.assertEqual([], get_bid_side(lob))
        self.assertEqual([], get_ask_side(lob))

    def test_compute_cumulative_qty(self):
        lob_ask_side = []
        cumulative_qtys = compute_cumulative_qty(lob_ask_side)
        self.assertEqual([], cumulative_qtys)

        lob_ask_side = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 25, 'price': 101.0}]
        cumulative_qtys = compute_cumulative_qty(lob_ask_side)
        self.assertEqual([25], cumulative_qtys)

        lob_ask_side = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 25, 'price': 101.0},
                        {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Sell', 'size': 60, 'price': 100.0},
                        {'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Sell', 'size': 150, 'price': 99.0},
                        {'symbol': 'XBTUSD', 'id': 8795077200, 'side': 'Sell', 'size': 100, 'price': 98.0}]

        sorted_ask_side = get_ask_side(lob_ask_side)

        cumulative_qtys = compute_cumulative_qty(sorted_ask_side)
        self.assertEqual([100, 250, 310, 335], cumulative_qtys)

        lob_bid_side = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Buy', 'size': 25, 'price': 101.0},
                        {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Buy', 'size': 60, 'price': 100.0},
                        {'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Buy', 'size': 150, 'price': 99.0},
                        {'symbol': 'XBTUSD', 'id': 8795077200, 'side': 'Buy', 'size': 100, 'price': 98.0}]

        sorted_bid_side = get_bid_side(lob_bid_side)
        cumulative_qtys = compute_cumulative_qty(sorted_bid_side)
        self.assertEqual([25, 85, 235, 335], cumulative_qtys)

    def test_sell_mo_market_impact_function(self):
        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 50, 'price': 101.0},
               {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Sell', 'size': 40, 'price': 100.5},
               {'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Buy', 'size': 400, 'price': 100.0},
               {'symbol': 'XBTUSD', 'id': 8795077200, 'side': 'Buy', 'size': 200, 'price': 99.5}]

        self.assertAlmostEqual(0.0, sell_mo_market_impact_function(lob, 0))

        with self.assertRaises(ValueError):
            sell_mo_market_impact_function(lob, -1)

        self.assertAlmostEqual(0.25, sell_mo_market_impact_function(lob, 1))
        self.assertAlmostEqual(0.25, sell_mo_market_impact_function(lob, 399))
        self.assertAlmostEqual(0.25, sell_mo_market_impact_function(lob, 400))

        self.assertAlmostEqual(0.25 + 0.5, sell_mo_market_impact_function(lob, 401))
        self.assertAlmostEqual(0.25 + 0.5, sell_mo_market_impact_function(lob, 601))
        self.assertAlmostEqual(0.25 + 0.5, sell_mo_market_impact_function(lob, 1000))

        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 50, 'price': 101.0},
               {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Sell', 'size': 40, 'price': 100.5},
               ]
        self.assertIsNone(sell_mo_market_impact_function(lob, 1))
        self.assertIsNone(sell_mo_market_impact_function([], 1))

    def test_buy_mo_market_impact_function(self):
        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 50, 'price': 101.0},
               {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Sell', 'size': 40, 'price': 100.5},
               {'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Buy', 'size': 400, 'price': 100.0},
               {'symbol': 'XBTUSD', 'id': 8795077200, 'side': 'Buy', 'size': 200, 'price': 99.5}]

        self.assertAlmostEqual(0.0, buy_mo_market_impact_function(lob, 0))

        with self.assertRaises(ValueError):
            buy_mo_market_impact_function(lob, -1)

        self.assertAlmostEqual(0.25, buy_mo_market_impact_function(lob, 1))
        self.assertAlmostEqual(0.25, buy_mo_market_impact_function(lob, 39))
        self.assertAlmostEqual(0.25, buy_mo_market_impact_function(lob, 40))
        self.assertAlmostEqual(0.25 + 0.5, buy_mo_market_impact_function(lob, 41))
        self.assertAlmostEqual(0.25 + 0.5, buy_mo_market_impact_function(lob, 90))
        self.assertAlmostEqual(0.25 + 0.5, buy_mo_market_impact_function(lob, 91))
        self.assertAlmostEqual(0.25 + 0.5, buy_mo_market_impact_function(lob, 1000))

        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Buy', 'size': 50, 'price': 101.0},
               {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Buy', 'size': 40, 'price': 100.5},
               ]
        self.assertIsNone(buy_mo_market_impact_function(lob, 1))
        self.assertIsNone(buy_mo_market_impact_function([], 1))

    def test_buy_mo_inverse_market_impact(self):
        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 50, 'price': 101.0},
               {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Sell', 'size': 40, 'price': 100.5},
               {'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Buy', 'size': 400, 'price': 100.0},
               {'symbol': 'XBTUSD', 'id': 8795077200, 'side': 'Buy', 'size': 200, 'price': 99.5}]

        self.assertAlmostEqual(0.0, buy_mo_inverse_market_impact(lob, 0.0))
        self.assertAlmostEqual(0.0, buy_mo_inverse_market_impact(lob, 0.150))
        self.assertAlmostEqual(40.0, buy_mo_inverse_market_impact(lob, 0.25))
        self.assertAlmostEqual(40.0, buy_mo_inverse_market_impact(lob, 0.50))
        self.assertAlmostEqual(40.0, buy_mo_inverse_market_impact(lob, 0.74999))
        self.assertAlmostEqual(90.0, buy_mo_inverse_market_impact(lob, 0.75))
        self.assertAlmostEqual(FLOAT_INFINITY, buy_mo_inverse_market_impact(lob, 0.76))

    def test_sell_mo_inverse_market_impact(self):
        lob = [{'symbol': 'XBTUSD', 'id': 8795076950, 'side': 'Sell', 'size': 50, 'price': 101.0},
               {'symbol': 'XBTUSD', 'id': 8795077100, 'side': 'Sell', 'size': 40, 'price': 100.5},
               {'symbol': 'XBTUSD', 'id': 8795077150, 'side': 'Buy', 'size': 400, 'price': 100.0},
               {'symbol': 'XBTUSD', 'id': 8795077200, 'side': 'Buy', 'size': 200, 'price': 99.5}]

        self.assertAlmostEqual(0.0, sell_mo_inverse_market_impact(lob, 0.0))
        self.assertAlmostEqual(0.0, sell_mo_inverse_market_impact(lob, 0.150))
        self.assertAlmostEqual(400.0, sell_mo_inverse_market_impact(lob, 0.25))
        self.assertAlmostEqual(400.0, sell_mo_inverse_market_impact(lob, 0.50))
        self.assertAlmostEqual(400.0, sell_mo_inverse_market_impact(lob, 0.74999))
        self.assertAlmostEqual(600.0, sell_mo_inverse_market_impact(lob, 0.75))
        self.assertAlmostEqual(FLOAT_INFINITY, sell_mo_inverse_market_impact(lob, 0.76))


if __name__ == '__main__':
    unittest.main()
