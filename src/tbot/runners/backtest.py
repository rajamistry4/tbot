"""Minimal candle runner. Signals fill on the NEXT candle open."""
from tbot.core.models import Order, RunResult


class BacktestRunner:
    def __init__(self, data, strategy, broker, risk):
        self.data, self.strategy = data, strategy
        self.broker, self.risk = broker, risk

    def run(self):
        fills, curve = [], []
        pending = None
        previous_time = None
        symbol = None
        for candle in self.data.candles():
            if candle.timestamp.tzinfo is None:
                raise ValueError("Candle timestamps must be timezone-aware")
            if previous_time is not None and candle.timestamp <= previous_time:
                raise ValueError("Candles must have strictly increasing timestamps")
            if symbol is not None and candle.symbol != symbol:
                raise ValueError("Demo runner supports one instrument")
            symbol, previous_time = candle.symbol, candle.timestamp
            if pending is not None:
                portfolio = self.broker.snapshot(candle.open)
                if self.risk.approve(pending, portfolio):
                    fills.append(self.broker.execute(pending, candle))
                pending = None
            portfolio = self.broker.snapshot(candle.close)
            curve.append((candle.timestamp, portfolio.equity))
            signal = self.strategy.on_candle(candle, portfolio)
            if signal is not None:
                if signal.symbol != candle.symbol:
                    raise ValueError("Strategy signal has the wrong instrument")
                pending = Order(signal.symbol, signal.side, signal.quantity)
        if not curve:
            raise ValueError("No candles supplied")
        # A final-candle signal has no next open and remains unfilled.
        # Open holdings are marked to the final close, not forcibly liquidated.
        return RunResult(self.broker.initial_cash, portfolio, tuple(fills), tuple(curve))
