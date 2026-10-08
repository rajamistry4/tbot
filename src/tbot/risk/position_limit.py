from decimal import Decimal
from tbot.core.interfaces import RiskManager
from tbot.core.models import Side


class PositionLimit(RiskManager):
    def __init__(self, max_quantity="1"):
        self.max_quantity = Decimal(str(max_quantity))
        if not self.max_quantity.is_finite() or self.max_quantity <= 0:
            raise ValueError("max_quantity must be finite and positive")

    def approve(self, order, portfolio):
        if not order.quantity.is_finite() or order.quantity <= 0:
            return False
        change = order.quantity if order.side == Side.BUY else -order.quantity
        return 0 <= portfolio.quantity + change <= self.max_quantity
