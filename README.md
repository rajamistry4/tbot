# tbot

A local, readable Python trading platform. Target integrations: Delta Exchange
India first, Zerodha second. Sprint 1 provides plugin contracts and a runnable
synthetic backtest. Sprint 2 adds public Delta India market data, Parquet caching,
and completed-candle REST polling. It does not place live orders.

## Windows setup (PowerShell)

Install Python 3.11 or newer. Open PowerShell in this repository:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m tbot --config config/demo.toml
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Using the virtual environment executable directly avoids PowerShell activation
policy changes. The demo writes `outputs/demo/report.json`. Run again to reproduce
the same result; that report is overwritten. Use another output directory to keep
separate runs. No API keys are needed. Installation includes PyArrow for Parquet storage.

Linux/macOS equivalent:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m tbot --config config/demo.toml
.venv/bin/python -m unittest discover -s tests -v
```

## How the example works

1. `cli.py` reads TOML configuration and constructs plugins from an explicit registry.
2. The data provider supplies completed, timezone-aware candles in time order.
3. The strategy receives each candle and the portfolio, then optionally returns a signal.
4. On the next candle, the risk manager checks the pending order.
5. The simulated broker fills the approved order at that candle's opening price.
6. The report saves fills, fees, equity history, and net P&L.

Prices and quantities use `Decimal`. Configuration uses strings for money and
quantity so precision is preserved. Paths in configuration are relative to the
configuration file, not your terminal directory. `timeframe_minutes = 60` is the
default; changing it changes the synthetic candle spacing, not real market data.

The foundation demo is single-instrument, long-only, and unleveraged. It charges
percentage fees but does not model slippage, futures contract sizes, margin,
liquidation, funding, partial fills, or exchange restrictions. Final holdings are
valued at the last close; final-candle signals remain unfilled. Insufficient cash
raises an error. Risk-rejected orders are discarded. These assumptions are not
sufficient for evaluating Delta futures strategies.

## Read and edit the code

Start with `config/demo.toml`, then `src/tbot/strategies/moving_average.py`, followed
by `src/tbot/runners/backtest.py`. Shared types live in `core/models.py`; plugin
contracts live in `core/interfaces.py`. See [the extension guide](docs/plugins.md)
and [the sprint roadmap](docs/roadmap.md).

See [Delta India data instructions](docs/delta_india_data.md) for historical
downloads, offline replay, timeframe configuration, and live candle polling.

Trainer is currently an interface only. Optimization, ML, charts, API, dashboard,
live broker execution, and restart recovery are later sprint deliverables. Never store API keys in committed configuration files.
