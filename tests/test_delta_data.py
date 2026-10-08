"""Offline contract tests. These do not claim the real exchange is reachable."""
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from tbot.cli import run_config
from tbot.data.cache import CandleCache
from tbot.data.delta_client import DeltaAPIError, DeltaIndiaClient
from tbot.data.delta_india import DeltaIndiaDataProvider, DeltaIndiaPollingFeed
from tbot.data.timeframes import native_interval

START = 1735689600  # 2025-01-01 00:00 UTC


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def row(timestamp, price='100.123456789123456789'):
    return dict(time=timestamp, open=price, high='110', low='90', close='101', volume='0.1')


class FakeClient:
    def __init__(self):
        self.calls = []
        self.mutate = lambda rows: rows

    def candles(self, symbol, resolution, start, end):
        self.calls.append((symbol, resolution, start, end))
        minutes = {'1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60}[resolution]
        # API responses may be newest-first, with an inclusive end candle.
        return self.mutate([row(t) for t in reversed(range(start, end + 1, minutes * 60))])


class DeltaDataTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.client = FakeClient()

    def provider(self, count=3, minutes=60, **kwargs):
        return DeltaIndiaDataProvider('BTCUSD', iso(START), iso(START + count * minutes * 60),
                                      minutes, self.directory.name, client=self.client, **kwargs)

    def test_sort_completed_range_and_exact_decimal_cache_replay(self):
        candles = list(self.provider().candles())
        self.assertEqual(len(candles), 3)
        self.assertEqual(candles[0].timestamp.timestamp(), START)
        self.assertEqual(candles[-1].timestamp.timestamp(), START + 7200)
        self.assertEqual(candles[0].open, Decimal('100.123456789123456789'))
        self.client.calls.clear()
        self.assertEqual(list(self.provider(offline=True).candles()), candles)
        self.assertEqual(self.client.calls, [])
        self.assertTrue(list(Path(self.directory.name).glob('*.parquet')))
        self.assertTrue((Path(self.directory.name) / 'index.sqlite3').exists())

    def test_chunking_does_not_truncate_large_request(self):
        candles = list(self.provider(count=501).candles())
        self.assertEqual(len(candles), 501)
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual(self.client.calls[0][3], self.client.calls[1][2])

    def test_non_native_aggregation(self):
        candles = list(self.provider(count=2, minutes=10).candles())
        self.assertEqual(self.client.calls[0][1], '5m')
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].volume, Decimal('0.2'))
        self.assertEqual(candles[0].open, Decimal('100.123456789123456789'))
        self.assertEqual(candles[0].high, Decimal(110))
        self.assertEqual(candles[0].low, Decimal(90))
        self.assertEqual(candles[0].close, Decimal(101))
        self.assertEqual(native_interval(7), (1, '1m'))

    def test_missing_candle_is_not_cached(self):
        self.client.mutate = lambda rows: [r for r in rows if r['time'] != START + 3600]
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            list(self.provider().candles())
        with self.assertRaisesRegex(ValueError, 'No exact cached'):
            list(self.provider(offline=True).candles())

    def test_conflicting_duplicate_is_rejected(self):
        self.client.mutate = lambda rows: rows + [row(START, '99')]
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            list(self.provider().candles())

    def test_invalid_ohlcv_is_rejected(self):
        for field, value in [('high', '1'), ('volume', '-1'), ('open', 'NaN')]:
            def mutate(rows, field=field, value=value):
                for entry in rows:
                    entry[field] = value
                return rows
            self.client.mutate = mutate
            with self.subTest(field=field), self.assertRaises(ValueError):
                list(self.provider().candles())

    def test_range_configuration_errors(self):
        for kwargs in [dict(start='2025-01-01T00:00:00'),
                       dict(start='2025-01-01T00:01:00Z'),
                       dict(end='2024-12-31T00:00:00Z'),
                       dict(timeframe_minutes=0), dict(timeframe_minutes=True),
                       dict(offline=True, refresh=True)]:
            settings = dict(symbol='BTCUSD', start=iso(START), end=iso(START + 3600),
                            cache_directory=self.directory.name)
            settings.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                DeltaIndiaDataProvider(**settings)

    def test_current_unfinished_candle_is_rejected(self):
        now = int(datetime.now(timezone.utc).timestamp()) // 3600 * 3600
        provider = DeltaIndiaDataProvider('BTCUSD', iso(now), iso(now + 3600),
                                          cache_directory=self.directory.name, client=self.client)
        with self.assertRaisesRegex(ValueError, 'unfinished'):
            list(provider.candles())

    def test_refresh_replaces_dataset_and_offline_cache_miss(self):
        with self.assertRaisesRegex(ValueError, 'No exact cached'):
            list(self.provider(offline=True).candles())
        first = list(self.provider().candles())
        self.client.mutate = lambda rows: [dict(r, close='102') for r in rows]
        second = list(self.provider(refresh=True).candles())
        self.assertNotEqual(first, second)
        self.assertEqual(list(self.provider(offline=True).candles()), second)

    def test_corrupt_cached_prices_are_revalidated(self):
        provider = self.provider()
        candles = list(provider.candles())
        from dataclasses import replace
        candles[0] = replace(candles[0], low=Decimal(999))
        provider.cache.save(provider.request, candles)
        with self.assertRaisesRegex(ValueError, 'OHLC'):
            list(self.provider(offline=True).candles())

    def test_polling_emits_only_closed_candles_without_duplicates(self):
        clock = [START + 3600 + 100]
        def sleep(seconds):
            clock[0] = START + 7200 + 100
        feed = DeltaIndiaPollingFeed('BTCUSD', iso(START), cache_directory=self.directory.name,
            client=self.client, clock=lambda: clock[0], sleep=sleep)
        stream = feed.candles()
        first, second = next(stream), next(stream)
        self.assertEqual(first.timestamp.timestamp(), START)
        self.assertEqual(second.timestamp.timestamp(), START + 3600)
        self.assertEqual(feed.next_start, START + 7200)
        stream.close()

    def test_configured_backtest_replays_delta_cache(self):
        provider = self.provider(count=24)
        list(provider.candles())
        template = Path('config/delta_india.toml').read_text()
        template = template.replace('../data/cache', 'cache').replace('offline = false', 'offline = true')
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / 'delta.toml'
            config.write_text(template)
            import shutil
            shutil.copytree(self.directory.name, Path(root) / 'cache')
            result, report = run_config(config)
            self.assertEqual(len(result.equity_curve), 24)
            self.assertTrue(report.is_file())


class DeltaHTTPTests(unittest.TestCase):
    def response(self, payload):
        return io.BytesIO(json.dumps(payload).encode())

    @patch('tbot.data.delta_client.urlopen')
    def test_public_request_parameters(self, open_url):
        open_url.return_value = self.response({'success': True, 'result': []})
        self.assertEqual(DeltaIndiaClient().candles('BTCUSD', '1h', 1, 2), [])
        request = open_url.call_args.args[0]
        self.assertIn('https://api.india.delta.exchange/v2/history/candles?', request.full_url)
        self.assertIn('resolution=1h', request.full_url)
        self.assertNotIn('Authorization', request.headers)

    @patch('tbot.data.delta_client.urlopen')
    def test_json_numeric_precision_is_preserved(self, open_url):
        open_url.return_value = io.BytesIO(
            b'{"success": true, "result": [{"close": 100.123456789123456789}]}')
        rows = DeltaIndiaClient().candles('BTCUSD', '1h', 1, 2)
        self.assertEqual(rows[0]['close'], Decimal('100.123456789123456789'))

    @patch('tbot.data.delta_client.time.sleep')
    @patch('tbot.data.delta_client.urlopen')
    def test_rate_limit_retry(self, open_url, sleep):
        open_url.side_effect = [HTTPError('url', 429, 'limit', {'Retry-After': '1'}, None),
                               self.response({'success': True, 'result': []})]
        self.assertEqual(DeltaIndiaClient().candles('BTCUSD', '1h', 1, 2), [])
        sleep.assert_called_once_with(1)

    @patch('tbot.data.delta_client.urlopen')
    def test_access_denial_is_not_retried(self, open_url):
        open_url.side_effect = HTTPError('url', 403, 'blocked', {}, None)
        with self.assertRaisesRegex(DeltaAPIError, '403'):
            DeltaIndiaClient().get('/v2/products')
        self.assertEqual(open_url.call_count, 1)

    @patch('tbot.data.delta_client.time.sleep')
    @patch('tbot.data.delta_client.urlopen')
    def test_network_failure_is_bounded(self, open_url, sleep):
        open_url.side_effect = URLError('unavailable')
        with self.assertRaises(DeltaAPIError):
            DeltaIndiaClient().get('/v2/products')
        self.assertEqual(open_url.call_count, 3)

    @patch('tbot.data.delta_client.urlopen')
    def test_api_failure_and_invalid_json(self, open_url):
        for response in [self.response({'success': False, 'error': {'code': 'bad_symbol'}}),
                         io.BytesIO(b'not json')]:
            open_url.return_value = response
            with self.assertRaises(DeltaAPIError):
                DeltaIndiaClient().get('/v2/products')

    @patch('tbot.data.delta_client.urlopen')
    def test_instrument_pagination(self, open_url):
        open_url.side_effect = [self.response({'success': True, 'result': [{'symbol': 'BTCUSD'}], 'meta': {'after': 'next'}}),
                               self.response({'success': True, 'result': [{'symbol': 'ETHUSD'}], 'meta': {'after': None}})]
        self.assertEqual(len(DeltaIndiaClient().products()), 2)
        self.assertIn('after=next', open_url.call_args.args[0].full_url)

    @patch('tbot.data.delta_client.urlopen')
    def test_repeated_pagination_cursor_fails(self, open_url):
        open_url.side_effect = [self.response({'success': True, 'result': [], 'meta': {'after': 'same'}})
                               for _ in range(2)]
        with self.assertRaisesRegex(DeltaAPIError, 'repeated'):
            DeltaIndiaClient().products()


if __name__ == '__main__':
    unittest.main()
