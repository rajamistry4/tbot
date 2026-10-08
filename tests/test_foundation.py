import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

from tbot.cli import run_config
from tbot.core.interfaces import DataProvider, Strategy
from tbot.core.models import Candle, Order, Side, Signal
from tbot.core.plugins import PluginRegistry
from tbot.brokers.simulated import SimulatedBroker
from tbot.risk.position_limit import PositionLimit
from tbot.runners.backtest import BacktestRunner
from tbot.reporting.json_report import JsonReport


def candle(hour, price):
    return Candle(datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hour),
                  'BTCUSD', D(price), D(price), D(price), D(price), D(1))


class TestData(DataProvider):
    def __init__(self, values):
        self.values = values

    def candles(self):
        return iter(self.values)


class BuyOnce(Strategy):
    def __init__(self):
        self.called = False

    def on_candle(self, candle, portfolio):
        if not self.called:
            self.called = True
            return Signal(candle.symbol, Side.BUY, D(1))


class FoundationTests(unittest.TestCase):
    def run_example(self, values, limit='1'):
        return BacktestRunner(TestData(values), BuyOnce(),
                              SimulatedBroker('1000', '0.01'), PositionLimit(limit)).run()

    def test_next_open_fill_and_mark_to_market(self):
        result = self.run_example([candle(0, '100'), candle(1, '120'), candle(2, '130')])
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.fills[0].price, D(120))
        self.assertEqual(result.fills[0].timestamp, candle(1, '120').timestamp)
        self.assertEqual(result.final_portfolio.cash, D('878.8'))
        self.assertEqual(result.final_portfolio.equity, D('1008.8'))

    def test_last_signal_is_not_filled(self):
        self.assertEqual(self.run_example([candle(0, '100')]).fills, ())

    def test_risk_rejects_oversized_order(self):
        result = self.run_example([candle(0, '100'), candle(1, '120')], '0.5')
        self.assertEqual(result.fills, ())
        self.assertEqual(result.final_portfolio.cash, D(1000))

    def test_sell_accounting_and_rejection_is_atomic(self):
        broker = SimulatedBroker('1000', '0.01')
        broker.execute(Order('BTCUSD', Side.BUY, D(2)), candle(0, '100'))
        broker.execute(Order('BTCUSD', Side.SELL, D(2)), candle(1, '120'))
        self.assertEqual(broker.cash, D('1035.6'))
        before = broker.snapshot(D(120))
        with self.assertRaises(ValueError):
            broker.execute(Order('BTCUSD', Side.SELL, D(1)), candle(2, '120'))
        self.assertEqual(broker.snapshot(D(120)), before)

    def test_reject_empty_and_unordered_data(self):
        for values in ([], [candle(1, '100'), candle(0, '100')]):
            with self.assertRaises(ValueError):
                self.run_example(values)

    def test_registry_contract_and_duplicate_checks(self):
        registry = PluginRegistry()
        with self.assertRaises(TypeError):
            registry.register('strategy', 'bad', TestData)
        registry.register('strategy', 'buy_once', BuyOnce)
        self.assertIsInstance(registry.create('strategy', {'name': 'buy_once'}), BuyOnce)
        with self.assertRaises(ValueError):
            registry.register('strategy', 'buy_once', BuyOnce)
        with self.assertRaises(ValueError):
            registry.create('strategy', {'name': 'missing'})

    def test_config_and_report_end_to_end(self):
        template = Path('config/demo.toml').read_text()
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'demo.toml'
            config.write_text(template.replace('../outputs/demo', 'reports'))
            result, report = run_config(config)
            self.assertEqual(len(result.equity_curve), 14)
            self.assertEqual(len(result.fills), 3)
            payload = json.loads(report.read_text())
            self.assertEqual(payload['final_equity'], str(result.final_portfolio.equity))
            self.assertEqual(payload['fill_count'], 3)
            self.assertEqual(report.parent, Path(directory) / 'reports')
            first = report.read_text()
            JsonReport().generate(result, report.parent)
            self.assertEqual(first, report.read_text())

    def test_live_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'live.toml'
            config.write_text('[run]\nmode = "live"\n')
            with self.assertRaisesRegex(ValueError, 'Only backtest'):
                run_config(config)


if __name__ == '__main__':
    unittest.main()
