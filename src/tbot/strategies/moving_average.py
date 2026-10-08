"""A small example you can copy to create another strategy."""
from collections import deque
from decimal import Decimal
from tbot.core.interfaces import Strategy
from tbot.core.models import Side, Signal


class MovingAverageStrategy(Strategy):
    def __init__(self, window=3, quantity="1"):
        if not isinstance(window, int) or window < 2:
            raise ValueError("window must be an integer of at least 2")
        self.prices = deque(maxlen=window)
        self.quantity = Decimal(str(quantity))
        if not self.quantity.is_finite() or self.quantity <= 0:
            raise ValueError("quantity must be finite and positive")

    def on_candle(self, candle, portfolio):
        self.prices.append(candle.close)
        if len(self.prices) < self.prices.maxlen:
            return None
        average = sum(self.prices) / len(self.prices)
        if candle.close > average and portfolio.quantity == 0:
            return Signal(candle.symbol, Side.BUY, self.quantity)
        if candle.close < average and portfolio.quantity > 0:
            return Signal(candle.symbol, Side.SELL, portfolio.quantity)
        return None
