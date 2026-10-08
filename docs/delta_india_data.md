# Delta Exchange India market data

This adapter reads public endpoints on `https://api.india.delta.exchange`.
No API key is needed. India and global Delta have different instruments and
identifiers; this adapter deliberately targets India only.

## Windows commands

Run from the repository directory after completing README setup. Refresh the
installation to install the Sprint 2 dependency:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

Download instrument metadata. The output retains exchange fields including
product IDs, symbols, contract types, contract values, price/size steps, and state
when provided by the API. Decimal numbers are stored as strings to retain precision.
Check the instrument's state and contract type before selecting it.

```powershell
.\.venv\Scripts\python.exe -m tbot.data.commands instruments --symbol BTCUSD
```

Download and validate a full day of hourly candles:

```powershell
.\.venv\Scripts\python.exe -m tbot.data.commands fetch --symbol BTCUSD --start 2025-01-01T00:00:00Z --end 2025-01-02T00:00:00Z
```

Replay exactly that dataset with the network disabled in the adapter:

```powershell
.\.venv\Scripts\python.exe -m tbot.data.commands fetch --symbol BTCUSD --start 2025-01-01T00:00:00Z --end 2025-01-02T00:00:00Z --offline
```

Try ten-minute candles (aggregated from native five-minute candles):

```powershell
.\.venv\Scripts\python.exe -m tbot.data.commands fetch --symbol BTCUSD --start 2025-01-01T00:00:00Z --end 2025-01-02T00:00:00Z --timeframe-minutes 10
```

Run the educational strategy example on real historical prices:

```powershell
.\.venv\Scripts\python.exe -m tbot --config config/delta_india.toml
```

Edit `offline = true` in that config to run from cache; set `refresh = true` to
replace the exact dataset with a fresh download. Do not enable both. Configuration
paths are relative to the TOML file. Command-line paths are relative to your
terminal directory. The sample broker remains a cash simulator, **not a Delta
futures simulator**; its report is not suitable for evaluating leveraged trading.

## Candle timing and data quality

- Start is inclusive and end is exclusive. A candle's timestamp is its opening
  time; it is available to strategies only after the interval completes.
- Dates require a timezone and whole seconds. `Z` means UTC. Indian local time
  can be expressed as `2025-01-01T05:30:00+05:30`, equivalent to midnight UTC.
- Boundaries align to multiples of the timeframe since the UTC Unix epoch.
  Hourly intervals therefore use UTC whole hours. Weekly or unusual multi-day
  intervals also use epoch alignment, not an exchange calendar.
- Any positive whole number of minutes is supported through aggregation.
  Native choices are 1m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, and 1d; the largest
  native interval dividing the target is chosen. This does not provide tick data
  or sub-minute intervals. Unusual intervals may require many API requests.
- Requests are split into batches of at most 500 source candles. Responses are
  sorted; identical duplicates are deduplicated; conflicting duplicates fail.
- Missing, misaligned, malformed, nonfinite, or inconsistent candles fail the
  request. Missing data is never filled with invented prices. A newly listed or
  inactive instrument may not cover the requested range: choose a valid range.
- Incomplete current candles are excluded. API requests use timeouts and bounded
  retries for rate limits and transient server/network errors. Access denials
  and invalid responses fail immediately.

## Local storage

`data/cache/` contains immutable Parquet files and `index.sqlite3`. The index
records provider, symbol, timeframe, exact start/end, schema version, row count,
and save time. Decimal values are stored as strings; they are not rounded to
floating-point values. Cached candles are validated again before replay.

An overlapping cached range does not satisfy a different exact request in this
version. `--refresh` updates the index to point to a new file; older files remain
so concurrent readers are safe. Data files, metadata downloads, and SQLite
indexes are ignored by Git. Delete the cache directory only when no process is
using it. Back up it separately if you want to retain downloaded datasets.

## Live candle polling

This is REST polling of completed candles, not websocket streaming and not live
order execution. Pick a recent completed hour, expressed in UTC:

```powershell
$start = [DateTimeOffset]::UtcNow.AddHours(-1).ToString("yyyy-MM-ddTHH:00:00'Z'")
.\.venv\Scripts\python.exe -m tbot.data.commands watch --symbol BTCUSD --start $start --count 3 --poll-seconds 10
```

The command catches up from start, then waits for new completed candles. It
prints three candles and exits; with hourly candles this may take hours. Ctrl+C
stops polling. Use `--timeframe-minutes 1` and an aligned recent minute for a
shorter trial. Only emitted candles advance the resume timestamp. To resume,
set start to the last emitted opening time plus one interval.

Polling fails visibly if a candle is missing, rather than skipping a gap. If the
exchange has not published a recently completed candle yet, retry after it is
available. Persistent automatic reconnect supervision belongs to Sprint 7.

## Verification and network requirements

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use simulated exchange responses and cover paging, numeric precision,
timeframe aggregation, caching, corruption detection, incomplete ranges, HTTP
retries, and live candle timing. They do not prove connectivity to the exchange.

Current cloud validation: the egress proxy rejects the India API with HTTP 403.
The required network-domain addition has been saved in the environment draft,
but not applied or published. Review and save it in environment settings and
publish the environment, then rerun the instrument and fetch commands. Local
Windows connectivity must be verified on your computer. No credential is needed
to resolve this public-data access restriction.

Endpoint definitions follow the exchange's official client:
https://github.com/delta-exchange/python-rest-client (India base URL,
`/v2/products`, `/v2/history/candles`). API reference: https://docs.delta.exchange/.
The actual response contract and supported resolutions still need real-exchange
verification in an allowed environment.
