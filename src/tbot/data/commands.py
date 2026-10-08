"""Market-data commands. These never place orders or run a trading strategy."""
import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from .delta_client import DeltaIndiaClient, DeltaAPIError
from .delta_india import DeltaIndiaDataProvider, DeltaIndiaPollingFeed


def main():
    parser = argparse.ArgumentParser(description="Delta India public market data")
    commands = parser.add_subparsers(dest="command", required=True)
    products = commands.add_parser("instruments", help="Save instrument metadata")
    products.add_argument("--output", type=Path, default=Path("data/instruments.json"))
    products.add_argument("--symbol", help="Filter by exact instrument symbol")
    for name in ("fetch", "watch"):
        command = commands.add_parser(name)
        command.add_argument("--symbol", default="BTCUSD")
        command.add_argument("--start", required=True, help="Timezone-aware ISO date")
        command.add_argument("--timeframe-minutes", type=int, default=60)
        command.add_argument("--cache-directory", type=Path, default=Path("data/cache"))
        if name == "fetch":
            command.add_argument("--end", required=True, help="Exclusive timezone-aware end")
            command.add_argument("--offline", action="store_true")
            command.add_argument("--refresh", action="store_true")
        else:
            command.add_argument("--count", type=int, default=1)
            command.add_argument("--poll-seconds", type=float, default=10)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        if args.command == "instruments":
            rows = DeltaIndiaClient().products()
            if args.symbol:
                rows = [row for row in rows if row.get("symbol") == args.symbol]
            if not rows:
                raise ValueError("No matching instruments")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(dict(provider="delta_india",
                fetched_at=datetime.now(timezone.utc).isoformat(), products=rows), indent=2, default=str), encoding="utf-8")
            print(f"Saved {len(rows)} instruments to {args.output}")
        elif args.command == "fetch":
            provider = DeltaIndiaDataProvider(args.symbol, args.start, args.end,
                args.timeframe_minutes, args.cache_directory, args.offline, args.refresh)
            candles = list(provider.candles())
            print(f"Validated {len(candles)} candles: {candles[0].timestamp.isoformat()} to {candles[-1].timestamp.isoformat()}")
        else:
            if args.count <= 0:
                raise ValueError("count must be positive")
            feed = DeltaIndiaPollingFeed(args.symbol, args.start, args.timeframe_minutes,
                                        args.cache_directory, args.poll_seconds)
            for index, candle in enumerate(feed.candles(), start=1):
                print(f"{candle.timestamp.isoformat()} {candle.symbol} close={candle.close}", flush=True)
                if index >= args.count:
                    break
    except (DeltaAPIError, ValueError, OSError) as error:
        parser.exit(1, f"Data error: {error}\n")
    except KeyboardInterrupt:
        print("Stopped market-data polling.")


if __name__ == "__main__":
    main()
