import unittest
import typing as t
import orders

class TestSplitIntQuantity(unittest.TestCase):
    def check_invariants(self, expected_sum: int, parts: int, diff: int, actual: t.List[int]):
        # print(f'check_invariants: actual: {actual}')
        self.assertEqual(len(actual), parts)
        self.assertEqual(expected_sum, sum(actual))
        for val in actual:
            # print(f'val: {val}, average: {expected_sum / parts}, diff: {diff}')
            self.assertGreaterEqual(val, 1)
            self.assertTrue(abs(int(val - expected_sum / parts)) <= diff)

    def test_diff_is_zero(self):
        sum, parts, diff = 10, 3, 0
        actual: t.List[int] = orders.split_int_quantity(sum, parts, diff)
        self.check_invariants(sum, parts, diff, actual)

    def test_diff_is_1(self):
        sum, parts, diff = 10, 3, 1
        actual: t.List[int] = orders.split_int_quantity(sum, parts, diff)
        self.check_invariants(sum, parts, diff, actual)

    def test_diff_is_2(self):
        sum, parts, diff = 10, 3, 2
        actual: t.List[int] = orders.split_int_quantity(sum, parts, diff)
        self.check_invariants(sum, parts, diff, actual)

    def test_num_of_parts_is_same_as_total_diff_is_5(self):
        sum, parts, diff = 10, 10, 5
        actual: t.List[int] = orders.split_int_quantity(sum, parts, diff)
        self.check_invariants(sum, parts, diff, actual)

    def test_num_of_parts_is_1_diff_is_2(self):
        sum, parts, diff = 10, 1, 5
        actual: t.List[int] = orders.split_int_quantity(sum, parts, diff)
        self.check_invariants(sum, parts, diff, actual)

    def test_num_of_parts_is_large(self):
        sum, parts, diff = 1000000, 10000, 500
        actual: t.List[int] = orders.split_int_quantity(sum, parts, diff)
        self.check_invariants(sum, parts, diff, actual)


class TestGenerateOrders(unittest.TestCase):
    def test_constraints_are_satisfied(self):
        req: orders.Request = orders.Request(symbol='BTCUSDT',
                                             usd_vol=10,
                                             usd_diff=1,
                                             splits=3,
                                             side=orders.Side.SELL,
                                             min_price=2,
                                             max_price=4)
        constraints: orders.Constraints = orders.Constraints(quantity_precision=5,
                                                             quantity_step_size=0.017,
                                                             price_step_size=0.07)

        actual: t.List[orders.Order] = orders.generate_orders(req, 3., constraints)
        self.assertEqual(req.splits, len(actual))
        self.assertEqual(req.splits, len({order.order_id for order in actual})) # all IDs are unique
        self.assertTrue(all(o.symbol == 'BTCUSDT' for o in actual))
        self.assertTrue(all(o.time_in_force == 'GTC' for o in actual))
        self.assertTrue(all(o.side == orders.Side.SELL for o in actual))
        self.assertTrue(all(o.type == 'LIMIT' for o in actual))

        for o in actual:
            # Check that quantity is a multiple of quantity_step_size
            self.assertEqual(round(o.quantity % constraints.quantity_step_size, 10) % constraints.quantity_step_size, 0.)
            # Check that price is a multiple of price_step_size
            self.assertEqual(round(o.price % constraints.price_step_size, 10) % constraints.price_step_size, 0.)


