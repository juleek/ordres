import enum
import uuid
import math
import random
import logging
import argparse
import traceback
import secret_api
import typing as t
import binance as binan
import dataclasses as dc
from logger import logger
import binance.exceptions as binanexc

# ======================================================================================================================
# Constants

KEY = secret_api.Key
SECRET = secret_api.Secret


# ======================================================================================================================
# Data-classes / enums / helpers

class Side(enum.Enum):
    SELL = enum.auto()
    BUY = enum.auto()

@dc.dataclass
class Constraints:
    """
    Creating price/volume is not an easy task, Binance has a number of constraints.
    This struct holds them.
    """
    quantity_precision: int # aka baseAssetPrecision
    quantity_step_size: float # aka {'filterType': 'LOT_SIZE', 'stepSize': '0.00000100'
    price_step_size: float # aka {'filterType': 'PRICE_FILTER', 'tickSize': '0.01000000'



@dc.dataclass
class Request:
    """
    Describes main incoming request
    """
    symbol: str
    usd_vol: float # "volume"
    usd_diff: float # "amountDif"
    splits: int # "number"
    side: Side
    min_price: float
    max_price: float



def fuzzy_equals(a, b, tolerance=1e-8):
    return abs(a - b) <= tolerance


@dc.dataclass
class CreationStatus:
    """
    Main result of our work
    """
    requested_base_quantity: float
    actual_base_quantity: float

    def is_ok(self):
        return fuzzy_equals(self.requested_base_quantity, self.actual_base_quantity)


@dc.dataclass
class Order:
    order_id: str
    symbol: str
    time_in_force: str
    quantity: float
    price: float
    side: Side
    type: str


# ======================================================================================================================
# Binance API wrapper (for retries)

MAX_RETRIES: int = 3

def create_order_with_retries(order: Order, client: binan.Client) -> CreationStatus:
    # /api/v3/order
    logger.info(f'Placing order = {order}')
    for i in range(MAX_RETRIES):
        try:
            client.create_order(
                newClientOrderId=order.order_id,
                type=order.type,
                symbol=order.symbol,
                side=order.side.name,
                timeInForce=order.time_in_force,
                quantity=order.quantity, # base asset
                price=order.price)
            return CreationStatus(requested_base_quantity=order.quantity, actual_base_quantity=order.quantity)

        except binanexc.BinanceAPIException as e:
            if e.message == "Duplicate order sent.":
                # Interpret this as success
                return CreationStatus(requested_base_quantity=order.quantity, actual_base_quantity=order.quantity)
            logger.warning(f"Failed to place order: {e}. {'Giving up.' if i == MAX_RETRIES - 1 else 'Retrying...'}")
        except Exception as e:
            logger.warning(f"Failed to place order: {e}. {'Giving up.' if i == MAX_RETRIES - 1 else 'Retrying...'}")
            traceback.print_exc()
    return CreationStatus(requested_base_quantity=order.quantity, actual_base_quantity=0.)


def get_avg_price_with_retries(symbol: str, client: binan.Client) -> float:
    # /api/v3/avgPrice
    logger.info(f'Getting average price of: {symbol}')
    for i in range(MAX_RETRIES):
        try:
            dict: t.Dict = client.get_avg_price(symbol=symbol)
            result: float = float(dict['price'])
            logger.info(f'Got average price of {symbol}: {result}')
            return result
        except Exception as e:
            traceback.print_exc()
            logger.critical(f"Failed to get average price: {e}. {'Giving up.' if i == MAX_RETRIES - 1 else 'Retrying...'}")


def get_symbol_info_with_retries(symbol: str, client: binan.Client) -> Constraints:
    # /api/v3/exchangeInfo
    logger.info(f'Getting info of symbol: {symbol}')
    for i in range(MAX_RETRIES):
        try:
            dict: t.Optional[t.Dict] = client.get_symbol_info(symbol=symbol)
            logger.info(f'Got symbol info: {dict}')
            result: Constraints = Constraints(quantity_precision=8, quantity_step_size=0.000001, price_step_size=0.01)
            if dict:
                if 'baseAssetPrecision' in dict:
                    result.quantity_precision = int(dict['baseAssetPrecision'])
                if 'filters' in dict:
                    lot_size_filter = next((filter for filter in dict['filters'] if filter['filterType'] == 'LOT_SIZE'), None)
                    if lot_size_filter and 'stepSize' in lot_size_filter:
                        result.quantity_step_size = float(lot_size_filter['stepSize'])
                    price_filter = next((filter for filter in dict['filters'] if filter['filterType'] == 'PRICE_FILTER'), None)
                    if price_filter and 'tickSize' in price_filter:
                        result.price_step_size = float(price_filter['tickSize'])
            logger.info(f'Extracted the constraints: {result}')
            return result
        except Exception as e:
            traceback.print_exc()
            logger.critical(f"Failed to get symbol info: {e}. {'Giving up.' if i == MAX_RETRIES - 1 else 'Retrying...'}")



# ======================================================================================================================
# Application logic


def split_int_quantity(total: int, num_of_parts: int, diff: int) -> t.List[int]:
    assert total >= num_of_parts
    step: float = total / num_of_parts
    diff = min(diff, int(step / 2))  # diff cannot be larger than step, avoid negative results
    if diff % 2 == 1:
        diff -= 1 # Make it even

    values: t.List[int] = [0]
    for i in range(1, num_of_parts):
        min_v: float = step * i - diff / 2.
        max_v: float = step * i + diff / 2.
        values.append(random.randint(int(min_v), int(max_v)))
    values.append(total)
    result = [values[i] - values[i - 1] for i in range(1, len(values))]
    return result


def generate_orders(req: Request, avg_price: float, constraints: Constraints) -> t.List[Order]:
    result: t.List[Order] = []
    base_quantity: float = req.usd_vol / avg_price # 10000usd / 2000usd/btc = 5.254 BTC
    int_base_quantity: int = int(base_quantity / constraints.quantity_step_size) # 12345 satoshi
    base_quantity_diff: float = req.usd_diff / avg_price
    int_base_quantity_diff: int = int(base_quantity_diff / constraints.quantity_step_size) # 13 satoshi
    for int_quantity in split_int_quantity(int_base_quantity, req.splits, int_base_quantity_diff):
        quantity: float = round(int_quantity * constraints.quantity_step_size, constraints.quantity_precision)
        int_min_price: int = int(req.min_price / constraints.price_step_size)
        int_max_price: int = int(req.max_price / constraints.price_step_size)
        int_price: int = random.randint(int_min_price, int_max_price)
        price: float = round(int_price * constraints.price_step_size, int(-math.log10(constraints.price_step_size)) + 2)
        # print(f'int min price: {int_min_price}, int max price: {int_max_price}, int_price: {int_price}, price: {price}')
        order: Order = Order(symbol=req.symbol,
                             time_in_force=binan.Client.TIME_IN_FORCE_GTC,
                             order_id=str(uuid.uuid4()),
                             quantity=quantity,
                             price=price,
                             side=req.side,
                             type=binan.Client.ORDER_TYPE_LIMIT)
        result.append(order)
    return result





def process_request(req: Request, client: binan.Client) -> CreationStatus:
    avg_price: float = get_avg_price_with_retries(req.symbol, client)
    constraints: Constraints = get_symbol_info_with_retries(req.symbol, client)

    result: CreationStatus = CreationStatus(requested_base_quantity=0., actual_base_quantity=0.)
    for order in generate_orders(req, avg_price, constraints):
        sub_result: CreationStatus = create_order_with_retries(order, client)
        result.actual_base_quantity += sub_result.actual_base_quantity
        result.requested_base_quantity += sub_result.requested_base_quantity

    logger.info(f'Result of placing multiple orders: {result}')
    return result


if __name__ == "__main__":
    logger.setLevel(logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', type=str, help='Market pair', default="ETHUSDT")
    parser.add_argument('--volume', type=float, help='Volume in USDT', default=100.)
    parser.add_argument('--amountDif', type=float, help='USDT range within which the volume is randomly selected in both upward and downward directions.', default=1.)
    parser.add_argument('--number', type=int, help='Number of orders', default=2)
    parser.add_argument('--side', type=str, help='SELL or BUY', default=Side.SELL)
    parser.add_argument('--priceMin', type=float, help='Min price range.', default=1908 - 5)
    parser.add_argument('--priceMax', type=float, help='Max price range.', default=1908 + 5)
    args = parser.parse_args()

    client = binan.Client(KEY, SECRET, testnet=True)
    request: Request = Request(symbol=args.symbol, # 'ETHUSDT'
                               usd_vol=args.volume, # 100.
                               usd_diff=args.amountDif, # 1.
                               splits=args.number, # 2
                               side=args.side, # Side.SELL
                               min_price=args.priceMin, # 1908 - 5,
                               max_price=args.priceMax) # 1908 + 5

    process_request(request, client)
