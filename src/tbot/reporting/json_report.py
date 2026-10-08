import json
from tbot.core.interfaces import ReportGenerator


class JsonReport(ReportGenerator):
    def generate(self, result, output_directory):
        output_directory.mkdir(parents=True, exist_ok=True)
        path = output_directory / "report.json"
        payload = {
            "initial_cash": str(result.initial_cash),
            "final_equity": str(result.final_portfolio.equity),
            "net_pnl": str(result.final_portfolio.equity - result.initial_cash),
            "open_quantity": str(result.final_portfolio.quantity),
            "fill_count": len(result.fills),
            "fills": [dict(timestamp=f.timestamp.isoformat(), symbol=f.symbol,
                           side=f.side.value, quantity=str(f.quantity),
                           price=str(f.price), fee=str(f.fee)) for f in result.fills],
            "equity_curve": [dict(timestamp=t.isoformat(), equity=str(e))
                             for t, e in result.equity_curve],
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
