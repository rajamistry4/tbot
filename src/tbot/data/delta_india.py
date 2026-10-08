"""Historical candles and polling of newly completed Delta India candles."""
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tbot.core.interfaces import DataProvider
from tbot.core.models import Candle
from .cache import CandleCache
from .delta_client import DeltaIndiaClient
from .timeframes import aggregate, native_interval, parse_utc, validate_candles


class DeltaIndiaDataProvider(DataProvider):
    # 500 bars per request is deliberately conservative to avoid server truncation.
    BATCH_SIZE = 500

    def __init__(self, symbol, start, end, timeframe_minutes=60,
                 cache_directory="data/cache", offline=False, refresh=False, client=None):
        self.symbol = symbol
        self.start = int(parse_utc(start).timestamp())
        self.end = int(parse_utc(end).timestamp())
        self.minutes = timeframe_minutes
        self.base_minutes, self.resolution = native_interval(timeframe_minutes)
        self.step = timeframe_minutes * 60
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("symbol must be nonempty")
        if self.start < 0 or self.start >= self.end or self.start % self.step or self.end % self.step:
            raise ValueError("Date range must be increasing and aligned to UTC timeframe boundaries")
        if not isinstance(offline, bool) or not isinstance(refresh, bool) or (offline and refresh):
            raise ValueError("offline and refresh must be booleans and cannot both be enabled")
        self.offline, self.refresh = offline, refresh
        self.cache = CandleCache(cache_directory)
        self.client = client or DeltaIndiaClient()
        self.request = dict(provider="delta_india", schema_version=1, symbol=symbol,
                            start=self.start, end=self.end, timeframe_minutes=timeframe_minutes)

    def candles(self):
        if self.end > int(datetime.now(timezone.utc).timestamp()) // self.step * self.step:
            raise ValueError("Requested range includes an unfinished candle")
        if not self.refresh:
            cached = self.cache.load(self.request)
            if cached is not None:
                validate_candles(cached, self.symbol, self.step, self.start, self.end)
                logging.info("Replaying %s cached Delta candles", len(cached))
                return iter(cached)
        if self.offline:
            raise ValueError("No exact cached dataset found; fetch this range online first")
        base_step = self.base_minutes * 60
        candles = {}
        for start in range(self.start, self.end, self.BATCH_SIZE * base_step):
            end = min(start + self.BATCH_SIZE * base_step, self.end)
            logging.info("Fetching Delta %s %s [%s, %s)", self.symbol, self.resolution, start, end)
            rows = self.client.candles(self.symbol, self.resolution, start, end)
            for row in rows:
                try:
                    timestamp = int(row["time"])
                    if Decimal(str(row["time"])) != timestamp:
                        raise ValueError("Nonintegral candle time")
                    candle = Candle(datetime.fromtimestamp(timestamp, timezone.utc), self.symbol,
                                    *(Decimal(str(row[key])) for key in ("open", "high", "low", "close", "volume")))
                except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError) as error:
                    raise ValueError("Malformed Delta candle") from error
                # The API may include the exclusive end boundary; discard it.
                if not start <= timestamp < end:
                    continue
                if timestamp in candles and candles[timestamp] != candle:
                    raise ValueError("Conflicting duplicate candle")
                candles[timestamp] = candle
        ordered = [candles[key] for key in sorted(candles)]
        output = aggregate(ordered, self.symbol, self.base_minutes, self.minutes, self.start, self.end)
        self.cache.save(self.request, output)
        return iter(output)


class DeltaIndiaPollingFeed:
    """REST polling, not a websocket feed. Emits only completed candles.

    Start is an opening timestamp. A reconnect re-fetches the unfinished range;
    callers can resume from the last emitted timestamp + one interval.
    """
    def __init__(self, symbol, start, timeframe_minutes=60, cache_directory="data/cache",
                 poll_seconds=10, client=None, clock=time.time, sleep=time.sleep):
        native_interval(timeframe_minutes)
        if not isinstance(poll_seconds, (int, float)) or not 1 <= poll_seconds <= 60:
            raise ValueError("poll_seconds must be between 1 and 60")
        self.symbol, self.minutes = symbol, timeframe_minutes
        self.next_start = int(parse_utc(start).timestamp())
        self.step = timeframe_minutes * 60
        if self.next_start < 0 or self.next_start % self.step:
            raise ValueError("Feed start must align to UTC timeframe boundaries")
        self.cache_directory = Path(cache_directory)
        self.poll_seconds = poll_seconds
        self.client = client or DeltaIndiaClient()
        self.clock, self.sleep = clock, sleep

    def candles(self):
        while True:
            closed_end = int(self.clock()) // self.step * self.step
            if closed_end > self.next_start:
                # Bounded catch-up batches keep memory usage predictable.
                end = min(closed_end, self.next_start + self.step * 500)
                provider = DeltaIndiaDataProvider(
                    self.symbol, datetime.fromtimestamp(self.next_start, timezone.utc).isoformat(),
                    datetime.fromtimestamp(end, timezone.utc).isoformat(), self.minutes,
                    self.cache_directory, refresh=True, client=self.client)
                for candle in provider.candles():
                    self.next_start = int(candle.timestamp.timestamp()) + self.step
                    yield candle
            else:
                self.sleep(self.poll_seconds)
