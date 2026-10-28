"""Regenerate the website's JSON data (docs/data/) from state.json and backtest.json."""
import json, shutil
from common import *

DOCS = HERE / "docs"


def main():
    cfg = load_config()
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    st = json.loads((HERE / "state.json").read_text())
    px = st.get("last_prices", {})
    holdings, total = [], 0.0
    for p, pos in st["positions"].items():
        value = pos["cash"] + pos["qty"] * px.get(p, 0)
        total += value
        holdings.append({"asset": p, "cash": pos["cash"], "qty": pos["qty"], "price": px.get(p), "value": value})
    start = st["starting_cash_usd"]
    out = {"mode": "PAPER (fake money)", "starting_cash_usd": start, "created": st.get("created"),
           "last_updated": st.get("last_tick"), "ticks": st.get("ticks", 0), "data_source": st.get("data_source"),
           "params": {k: cfg[k] for k in ("fast_sma", "slow_sma", "fee_rate", "slippage_rate")},
           "total_value": total, "cash": sum(h["cash"] for h in holdings), "pnl": total - start, "pnl_pct": total / start - 1,
           "fees_paid": sum(t.get("fee_usd", 0) for t in st["trades"]),
           "holdings": holdings,
           "trades": sorted(st["trades"], key=lambda t: -t["ts"]),
           "decisions": sorted(st.get("decisions", []), key=lambda d: -d["ts"])[:300]}
    (DOCS / "data" / "portfolio.json").write_text(json.dumps(out, indent=1))
    if (HERE / "backtest.json").exists():
        shutil.copy(HERE / "backtest.json", DOCS / "data" / "backtest.json")
    if (HERE / "backtest.png").exists():
        shutil.copy(HERE / "backtest.png", DOCS / "backtest.png")
    print(f"Site data written to {DOCS / 'data'}")


if __name__ == "__main__":
    main()
