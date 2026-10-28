"""One live paper-trading step. Run hourly, e.g.:  python3 tick.py && ./publish.sh
Fake money only: no exchange account, no API keys, no real orders.
Set PUBLISH=1 to run ./publish.sh automatically after the tick."""
import json, os, subprocess, time
from common import *

STATE = HERE / "state.json"


def load_state(cfg):
    if STATE.exists():
        st = json.loads(STATE.read_text())
        for p in cfg["assets"]:  # assets added to config later start with no allocation
            st["positions"].setdefault(p, {"cash": 0.0, "qty": 0.0})
        st.setdefault("decisions", [])
        st.setdefault("last_prices", {})
        return st
    alloc = cfg["starting_cash_usd"] / len(cfg["assets"])
    now = time.time()
    return {"created": local(now, cfg), "created_ts": now, "starting_cash_usd": cfg["starting_cash_usd"],
            "positions": {p: {"cash": alloc, "qty": 0.0} for p in cfg["assets"]}, "trades": [],
            "decisions": [], "last_prices": {}, "ticks": 0}


def main():
    cfg = load_config()
    st = load_state(cfg)
    gran = cfg["granularity_seconds"]
    now = int(time.time())
    lines, total = [], 0.0
    for p in cfg["assets"]:
        raw, src = fetch_candles(p, now - (cfg["slow_sma"] + 10) * gran, now, gran)
        closed = closed_only(raw, gran, now)
        closes = [c[4] for c in closed]
        f, s = sma(closes, cfg["fast_sma"])[-1], sma(closes, cfg["slow_sma"])[-1]
        price = raw[-1][4]  # most recent price (still-forming candle) used for the fill
        pos = st["positions"][p]
        had = pos["qty"] > 0
        want = target_long(f, s)
        action, trade = "HOLD", None
        if want and pos["cash"] > 0:
            qty, fill, fee = buy_fill(pos["cash"], price, cfg)
            trade = {"side": "BUY", "price": fill, "qty": qty, "usd": pos["cash"], "fee_usd": fee}
            pos["qty"] += qty; pos["cash"] = 0.0; action = "BUY"
        elif want is False and pos["qty"] > 0:
            usd, fill, fee = sell_fill(pos["qty"], price, cfg)
            trade = {"side": "SELL", "price": fill, "qty": pos["qty"], "usd": usd, "fee_usd": fee}
            pos["cash"] += usd; pos["qty"] = 0.0; action = "SELL"
        reason = reason_text(p, action, f, s, cfg, had)
        base = {"time": local(now, cfg), "ts": now, "asset": p, "market_price": price,
                "sma_fast": f, "sma_slow": s, "reason": reason}
        if trade:
            st["trades"].append({**base, **trade})
        st["decisions"].append({**base, "action": action})
        st["last_prices"][p] = price
        value = pos["cash"] + pos["qty"] * price
        total += value
        lines.append(f"  {p:9s} {fmt_px(price):>11s} -> {action:4s} | value ${value:,.2f} | {reason}")
    st["ticks"] += 1
    st["last_tick"] = local(now, cfg)
    st["last_tick_ts"] = now
    st["last_total_value_usd"] = total
    st["data_source"] = src
    STATE.write_text(json.dumps(st, indent=2))
    start = st["starting_cash_usd"]
    print(f"Paper tick #{st['ticks']} at {local(now, cfg)}  (data: {src})")
    print("\n".join(lines))
    print(f"  TOTAL value ${total:,.2f}  ({(total/start-1)*100:+.2f}% vs ${start:,.0f} start), "
          f"{len(st['trades'])} trades so far")
    if os.environ.get("PUBLISH") == "1":
        subprocess.run([str(HERE / "publish.sh")], check=False)


if __name__ == "__main__":
    main()
