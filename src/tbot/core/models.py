"""Shared types. Adapters translate exchange-specific data into these models."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True)
class Candle:
    # timestamp is the UTC opening time; strategies only receive completed candles.
    timestamp: datetime
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


@dataclass(frozen=True)
class Signal:
    symbol: str
    side: Side
    quantity: Decimal


@dataclass(frozen=True)
class Order:
    symbol: str
    side: Side
    quantity: Decimal


@dataclass(frozen=True)
class Fill:
    timestamp: datetime
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    fee: Decimal


@dataclass(frozen=True)
class Portfolio:
    cash: Decimal
    quantity: Decimal
    equity: Decimal


@dataclass(frozen=True)
class RunResult:
    initial_cash: Decimal
    final_portfolio: Portfolio
    fills: tuple[Fill, ...]
    equity_curve: tuple[tuple[datetime, Decimal], ...]
