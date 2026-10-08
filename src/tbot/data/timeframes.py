"""UTC-aligned candle validation and aggregation. Never invent missing prices."""
from datetime import datetime, timezone
from decimal import Decimal
from tbot.core.models import Candle

# Select a native interval that divides the requested interval exactly.
NATIVE_MINUTES = {1: "1m", 5: "5m", 15: "15m", 30: "30m", 60: "1h",
                  120: "2h", 240: "4h", 360: "6h", 1440: "1d"}


def parse_utc(text):
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Dates must include a timezone, for example 2025-01-01T00:00:00Z")
    if value.microsecond:
        raise ValueError("Dates must use whole seconds")
    return value.astimezone(timezone.utc)


def native_interval(minutes):
    if isinstance(minutes, bool) or not isinstance(minutes, int) or minutes <= 0:
        raise ValueError("timeframe_minutes must be a positive integer")
    base = max(value for value in NATIVE_MINUTES if minutes % value == 0)
    return base, NATIVE_MINUTES[base]


def validate_candles(candles, symbol, step_seconds, start, end):
    """Require full coverage of [start, end), valid OHLCV, and no duplicate times."""
    expected_count = (end - start) // step_seconds
    if len(candles) != expected_count:
        raise ValueError(f"Incomplete candle data: expected {expected_count}, received {len(candles)}")
    for index, candle in enumerate(candles):
        expected_time = start + index * step_seconds
        if candle.timestamp.tzinfo is None or candle.timestamp.timestamp() != expected_time:
            raise ValueError(f"Missing, duplicate, or misaligned candle at {expected_time}")
        if candle.symbol != symbol:
            raise ValueError("Candle instrument does not match request")
        prices = (candle.open, candle.high, candle.low, candle.close)
        if not all(value.is_finite() and value > 0 for value in prices):
            raise ValueError("OHLC prices must be finite and positive")
        if candle.low > min(candle.open, candle.close) or candle.high < max(candle.open, candle.close) or candle.low > candle.high:
            raise ValueError("Invalid candle OHLC bounds")
        if not candle.volume.is_finite() or candle.volume < 0:
            raise ValueError("Volume must be finite and nonnegative")


def aggregate(candles, symbol, base_minutes, target_minutes, start, end):
    validate_candles(candles, symbol, base_minutes * 60, start, end)
    group_size = target_minutes // base_minutes
    output = []
    for index in range(0, len(candles), group_size):
        group = candles[index:index + group_size]
        if len(group) != group_size:
            raise ValueError("Incomplete aggregation bucket")
        output.append(Candle(group[0].timestamp, symbol, group[0].open,
                             max(c.high for c in group), min(c.low for c in group),
                             group[-1].close, sum((c.volume for c in group), Decimal(0))))
    validate_candles(output, symbol, target_minutes * 60, start, end)
    return output
