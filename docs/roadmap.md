# Roadmap

Target: Windows, local single-user operation, Delta Exchange India then Zerodha.
Candle strategies default to one hour. Support native intervals and aggregation
where required. Training includes parameter optimization and machine learning.

| Sprint | Scope | Exit check |
| --- | --- | --- |
| 1 | Models, interfaces, registry, configuration, synthetic demo | Reproducible configured run and accounting/timing tests |
| 2 | Delta India historical/live data, cache, instrument metadata, timeframes | Fetch and replay a checked dataset |
| 3 | Futures-aware backtests, fees, funding, slippage, margin and contracts | Verified accounting and no future-data leakage |
| 4 | FastAPI, React dashboard, charts, metrics and exports | Launch a backtest and inspect results in UI |
| 5 | Parameter search, chronological splits, walk-forward evaluation | Evaluate chosen parameters on untouched data |
| 6 | ML features, trainer plugins, saved model artifacts and inference | Train and evaluate an ML strategy reproducibly |
| 7 | Delta paper trading, live feed, risk limits and monitoring | Observe a continuous paper session |
| 8 | Delta live execution, durable state, reconciliation, recovery, kill switch | Controlled execution and restart recovery |
| 9 | Zerodha data and broker adapters | Switch supported integrations through configuration |

Sprint 2 implements a SQLite dataset index and Parquet historical candle files.
Run/experiment metadata will be added with later runner and training work.
Live data in Sprint 2 uses REST polling of completed candles; websocket streaming
can be added when the paper-trading runner is built.

Sprint 2 offline tests pass, but real-exchange validation is pending because the
cloud egress proxy currently rejects the Delta India domain.
Perpetual futures are the initial scope assumption; options require additional
pricing, expiry and simulation work. Windows instructions are provided in Sprint
1, but execution on a Windows machine must be verified there.
