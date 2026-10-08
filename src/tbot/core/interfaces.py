"""Implement these contracts to add a plugin without changing the runner."""
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from .models import Candle, Fill, Order, Portfolio, RunResult, Signal


class DataProvider(ABC):
    @abstractmethod
    def candles(self) -> Iterable[Candle]:
        """Yield completed candles in increasing timestamp order."""


class Strategy(ABC):
    @abstractmethod
    def on_candle(self, candle: Candle, portfolio: Portfolio) -> Signal | None:
        """Return a signal using only data received so far."""


class Broker(ABC):
    @abstractmethod
    def execute(self, order: Order, candle: Candle) -> Fill:
        """Execute an order and return its fill, or raise on rejection."""

    @abstractmethod
    def snapshot(self, mark_price) -> Portfolio:
        """Return current holdings valued at the supplied price."""


class RiskManager(ABC):
    @abstractmethod
    def approve(self, order: Order, portfolio: Portfolio) -> bool:
        """Return whether the proposed order stays within risk limits."""


class Trainer(ABC):
    @abstractmethod
    def train(self, candles: Iterable[Candle], output_directory: Path) -> Path:
        """Train or optimize using an explicit training dataset; return artifact path."""


class ReportGenerator(ABC):
    @abstractmethod
    def generate(self, result: RunResult, output_directory: Path) -> Path:
        """Save a report and return its path."""
