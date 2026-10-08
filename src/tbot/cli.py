import argparse
import logging
import tomllib
from pathlib import Path
from tbot.core.plugins import PluginRegistry
from tbot.data.synthetic import SyntheticDataProvider
from tbot.strategies.moving_average import MovingAverageStrategy
from tbot.brokers.simulated import SimulatedBroker
from tbot.risk.position_limit import PositionLimit
from tbot.reporting.json_report import JsonReport
from tbot.runners.backtest import BacktestRunner


def default_registry():
    registry = PluginRegistry()
    registry.register("data", "synthetic", SyntheticDataProvider)
    registry.register("strategy", "moving_average", MovingAverageStrategy)
    registry.register("broker", "simulated", SimulatedBroker)
    registry.register("risk", "position_limit", PositionLimit)
    registry.register("report", "json", JsonReport)
    return registry


def run_config(path: Path):
    with path.open("rb") as file:
        config = tomllib.load(file)
    if config["run"]["mode"] != "backtest":
        raise ValueError("Only backtest mode is implemented; live orders are unavailable")
    registry = default_registry()
    runner = BacktestRunner(*(registry.create(category, config[category])
                              for category in ("data", "strategy", "broker", "risk")))
    result = runner.run()
    output = Path(config["run"]["output_directory"])
    if not output.is_absolute():
        output = path.resolve().parent / output
    report = registry.create("report", config["report"]).generate(result, output)
    return result, report


def main():
    parser = argparse.ArgumentParser(description="Run a configured synthetic backtest")
    parser.add_argument("--config", type=Path, default=Path("config/demo.toml"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        result, report = run_config(args.config)
    except (ValueError, KeyError, TypeError, OSError, tomllib.TOMLDecodeError) as error:
        parser.exit(1, f"Configuration/run error: {error}\n")
    logging.info("Completed: %s fills; final equity %s; report %s",
                 len(result.fills), result.final_portfolio.equity, report)
