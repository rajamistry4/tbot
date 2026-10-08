"""Unleveraged, long-only accounting for the foundation demo.

This is NOT a Delta futures simulator: margin, contracts, liquidation and
funding will be implemented before a Delta backtest or live adapter is enabled.
"""
from decimal import Decimal
from tbot.core.interfaces import Broker
from tbot.core.models import Fill, Portfolio, Side


class SimulatedBroker(Broker):
    def __init__(self, initial_cash="10000", fee_rate="0.001"):
        self.cash = Decimal(str(initial_cash))
        self.initial_cash = self.cash
        self.fee_rate = Decimal(str(fee_rate))
        self.quantity = Decimal(0)
        self.symbol = None
        if not self.cash.is_finite() or self.cash <= 0:
            raise ValueError("initial_cash must be finite and positive")
        if not self.fee_rate.is_finite() or not 0 <= self.fee_rate < 1:
            raise ValueError("fee_rate must be between zero and one")

    def snapshot(self, mark_price):
        return Portfolio(self.cash, self.quantity, self.cash + self.quantity * mark_price)

    def execute(self, order, candle):
        if order.symbol != candle.symbol or (self.symbol and order.symbol != self.symbol):
            raise ValueError("Demo broker supports one matching instrument")
        if not order.quantity.is_finite() or order.quantity <= 0:
            raise ValueError("Order quantity must be finite and positive")
        price = candle.open
        if not price.is_finite() or price <= 0:
            raise ValueError("Execution price must be finite and positive")
        notional = price * order.quantity
        fee = notional * self.fee_rate
        if order.side == Side.BUY:
            if notional + fee > self.cash:
                raise ValueError("Insufficient simulated cash")
            self.cash -= notional + fee
            self.quantity += order.quantity
        elif order.side == Side.SELL:
            if order.quantity > self.quantity:
                raise ValueError("Cannot sell more than the simulated holding")
            self.cash += notional - fee
            self.quantity -= order.quantity
        else:
            raise ValueError("Unsupported order side")
        self.symbol = order.symbol
        return Fill(candle.timestamp, order.symbol, order.side, order.quantity, price, fee)
