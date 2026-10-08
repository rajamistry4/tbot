# Adding plugins

## Add a strategy

Create `src/tbot/strategies/my_strategy.py`. This example buys once and holds:

```python
from decimal import Decimal
from tbot.core.interfaces import Strategy
from tbot.core.models import Signal, Side

class BuyAndHold(Strategy):
    def __init__(self, quantity="1"):
        self.quantity = Decimal(quantity)
        self.sent = False

    def on_candle(self, candle, portfolio):
        if not self.sent:
            self.sent = True
            return Signal(candle.symbol, Side.BUY, self.quantity)
        return None
```

Import the class in `cli.py`, then register it in `default_registry()`:

```python
registry.register("strategy", "buy_and_hold", BuyAndHold)
```

Select it in your TOML file:

```toml
[strategy]
name = "buy_and_hold"
quantity = "1"
```

Create a fresh strategy instance for every run: indicator history and other
mutable state must not leak between experiments. Strategies cannot see future
candles and should not call broker APIs. Add meaningful tests for signal timing.

## Add other components

Subclass the corresponding contract in `core/interfaces.py`, implement its methods,
and register a named class. Configuration fields besides `name` become constructor
arguments, so keep constructor names clear and validate inputs. Unknown plugin
names fail instead of dynamically importing code from configuration.

- DataProvider: yield ordered, completed candles using shared models. Convert
  timestamps to UTC and map exchange instrument identifiers in the adapter.
- Broker: implement execution and portfolio snapshots. The current demo runner
  also expects `initial_cash`. A future asynchronous live runner will require
  richer order status and reconciliation contracts; do not attach a live broker
  to this synchronous demonstration runner.
- RiskManager: approve or reject proposed orders from current portfolio state.
- ReportGenerator: save reports into the supplied directory.
- Trainer: accept explicitly selected training candles and return an artifact
  path. It is not wired to the CLI yet. Optimization and ML trainers will share
  this contract, with evaluation data kept separate.

A new adapter or strategy needs one explicit registration; engine logic stays
unchanged. This small registry is intentional and easy to debug.
