"""Deterministic example data, not exchange prices."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from tbot.core.interfaces import DataProvider
from tbot.core.models import Candle


class SyntheticDataProvider(DataProvider):
    def __init__(self, symbol="BTCUSD", timeframe_minutes=60):
        if not isinstance(timeframe_minutes, int) or timeframe_minutes <= 0:
            raise ValueError("timeframe_minutes must be a positive integer")
        self.symbol = symbol
        self.interval = timedelta(minutes=timeframe_minutes)

    def candles(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        prices = [100, 101, 102, 103, 104, 103, 102, 101, 100, 99, 100, 102, 104, 106]
        for index, value in enumerate(prices):
            price = Decimal(value)
            yield Candle(start + index * self.interval, self.symbol, price,
                         price + 1, price - 1, price, Decimal(10))
