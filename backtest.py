"""Backtest the SMA crossover over the last N days of hourly candles. Usage: python3 backtest.py"""
import json, time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime
from zoneinfo import ZoneInfo
from common import *


def max_drawdown(eq):
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    return mdd


def run_asset(product, alloc, cfg):
    gran = cfg["granularity_seconds"]
    end = int(time.time()) // gran * gran
    start_bt = end - cfg["backtest_days"] * 86400
    warm = start_bt - (cfg["slow_sma"] + 5) * gran
    candles, src = fetch_candles(product, warm, end, gran)
    candles = closed_only(candles, gran)
    closes = [c[4] for c in candles]
    f, s = sma(closes, cfg["fast_sma"]), sma(closes, cfg["slow_sma"])
    idx = [i for i, c in enumerate(candles) if c[0] >= start_bt]

    cash, qty, entry_cost = alloc, 0.0, None
    trades, round_trips, eq_t, eq_s, eq_h = [], [], [], [], []
    # buy & hold: buy at first close in window, same fee+slippage
    hq, _, _ = buy_fill(alloc, closes[idx[0]], cfg)
    for i in idx:
        px = closes[i]
        want = target_long(f[i], s[i])
        if want and qty == 0:
            entry_cost = cash
            qty, fill, fee = buy_fill(cash, px, cfg); cash = 0.0
            trades.append(("BUY", candles[i][0], fill, fee, qty, entry_cost, f[i], s[i], px))
        elif want is False and qty > 0:
            cash, fill, fee = sell_fill(qty, px, cfg); qty = 0.0
            trades.append(("SELL", candles[i][0], fill, fee, trades[-1][4], cash, f[i], s[i], px))
            round_trips.append(cash - entry_cost)
        eq_t.append(candles[i][0]); eq_s.append(cash + qty * px); eq_h.append(hq * px)
    final = eq_s[-1]
    open_pos = qty > 0
    if open_pos:  # mark-to-market the open trade, counting the exit cost it would incur
        cash_if_sold, _, _ = sell_fill(qty, closes[idx[-1]], cfg)
        round_trips.append(cash_if_sold - entry_cost)
        final = cash_if_sold  # value as if liquidated now, same basis as buy&hold below
    hold_final = sell_fill(hq, closes[idx[-1]], cfg)[0]
    return dict(product=product, src=src, alloc=alloc, final=final, ret=final / alloc - 1,
                trades=len(trades), fees=sum(t[3] for t in trades),
                wins=sum(1 for r in round_trips if r > 0), rts=len(round_trips), open_pos=open_pos,
                mdd=max_drawdown(eq_s), hold_final=hold_final, hold_ret=hold_final / alloc - 1,
                hold_mdd=max_drawdown(eq_h), eq_t=eq_t, eq_s=eq_s, eq_h=eq_h,
                trade_rows=trades, first=candles[idx[0]][0], last=candles[idx[-1]][0],
                p0=closes[idx[0]], p1=closes[idx[-1]])


def write_json(cfg, res, cf, hf, comb_s, comb_h, W, R):
    tot = cfg["starting_cash_usd"]
    trades = []
    for r in res:
        for side, ts, fill, fee, qty, usd, fa, sl, px in r["trade_rows"]:
            trades.append({"time": local(ts, cfg), "ts": ts, "asset": r["product"], "side": side, "price": fill,
                           "market_price": px, "qty": qty, "usd": usd, "fee_usd": fee, "sma_fast": fa, "sma_slow": sl,
                           "reason": reason_text(r["product"], side, fa, sl, cfg, side == "SELL")})
    trades.sort(key=lambda t: -t["ts"])
    row = lambda r: {k: r[k] for k in ("product", "alloc", "final", "ret", "trades", "fees", "wins", "rts", "mdd",
                                         "hold_final", "hold_ret", "hold_mdd", "p0", "p1")}
    out = {"generated": local(time.time(), cfg), "window_start": local(res[0]["first"], cfg),
           "window_end": local(res[0]["last"], cfg), "data_source": res[0]["src"],
           "params": {k: cfg[k] for k in ("fast_sma", "slow_sma", "fee_rate", "slippage_rate", "starting_cash_usd", "backtest_days")},
           "assets": [row(r) for r in res],
           "combined": {"start": tot, "final": cf, "ret": cf / tot - 1, "trades": sum(r["trades"] for r in res),
                        "fees": sum(r["fees"] for r in res), "wins": W, "rts": R, "mdd": max_drawdown(comb_s),
                        "hold_final": hf, "hold_ret": hf / tot - 1, "hold_mdd": max_drawdown(comb_h)},
           "trades": trades}
    (HERE / "backtest.json").write_text(json.dumps(out, indent=1))


def main():
    cfg = load_config()
    alloc = cfg["starting_cash_usd"] / len(cfg["assets"])
    res = [run_asset(p, alloc, cfg) for p in cfg["assets"]]
    print(f"SMA {cfg['fast_sma']}/{cfg['slow_sma']} on {cfg['granularity_seconds']//3600}h candles, long-only, "
          f"fee {cfg['fee_rate']*100:.2f}%/trade, slippage {cfg['slippage_rate']*100:.2f}%")
    print(f"Data: {res[0]['src']}  Window: {local(res[0]['first'], cfg)} -> {local(res[0]['last'], cfg)}\n")
    for r in res:
        wr = f"{r['wins']}/{r['rts']} ({r['wins']/r['rts']*100:.0f}%)" if r["rts"] else "n/a"
        print(f"{r['product']}: price {fmt_px(r['p0'])} -> {fmt_px(r['p1'])}")
        print(f"  Strategy : ${r['final']:,.2f} ({r['ret']*100:+.2f}%), trades {r['trades']}, win rate {wr}"
              f"{' (incl. open position)' if r['open_pos'] else ''}, fees ${r['fees']:,.2f}, max DD {r['mdd']*100:.2f}%")
        print(f"  Buy&hold : ${r['hold_final']:,.2f} ({r['hold_ret']*100:+.2f}%), max DD {r['hold_mdd']*100:.2f}%")
    # combined (align on common timestamps)
    common_t = sorted(set(res[0]["eq_t"]).intersection(*[set(r["eq_t"]) for r in res[1:]]))
    maps = [(dict(zip(r["eq_t"], r["eq_s"])), dict(zip(r["eq_t"], r["eq_h"]))) for r in res]
    comb_s = [sum(m[0][t] for m in maps) for t in common_t]
    comb_h = [sum(m[1][t] for m in maps) for t in common_t]
    tot = cfg["starting_cash_usd"]
    cf, hf = sum(r["final"] for r in res), sum(r["hold_final"] for r in res)
    W, R = sum(r["wins"] for r in res), sum(r["rts"] for r in res)
    print(f"\nCOMBINED (${tot:,.0f} start):")
    print(f"  Strategy : ${cf:,.2f} ({(cf/tot-1)*100:+.2f}%), trades {sum(r['trades'] for r in res)}, "
          f"win rate {W}/{R} ({W/R*100 if R else 0:.0f}%), fees ${sum(r['fees'] for r in res):,.2f} ({sum(r['fees'] for r in res)/tot*100:.1f}% of starting balance), max DD {max_drawdown(comb_s)*100:.2f}%")
    print(f"  Buy&hold : ${hf:,.2f} ({(hf/tot-1)*100:+.2f}%), max DD {max_drawdown(comb_h)*100:.2f}%")

    tz = ZoneInfo(cfg["timezone"])
    fig, axes = plt.subplots(len(res) + 1, 1, figsize=(12, 4 * (len(res) + 1)), sharex=True)
    series = [(r["product"], r["eq_t"], r["eq_s"], r["eq_h"]) for r in res] + [("Combined", common_t, comb_s, comb_h)]
    for ax, (name, t, s_, h_) in zip(axes, series):
        dt = [datetime.fromtimestamp(x, tz) for x in t]
        ax.plot(dt, s_, label=f"SMA {cfg['fast_sma']}/{cfg['slow_sma']} strategy")
        ax.plot(dt, h_, label="Buy & hold", alpha=0.8)
        ax.set_title(f"{name}: equity (USD)"); ax.grid(alpha=0.3); ax.legend()
    axes[-1].set_xlabel(f"Time ({cfg['timezone']})")
    fig.tight_layout(); fig.savefig(HERE / "backtest.png", dpi=110)
    write_json(cfg, res, cf, hf, comb_s, comb_h, W, R)
    print(f"\nChart saved: {HERE / 'backtest.png'}")


if __name__ == "__main__":
    main()
