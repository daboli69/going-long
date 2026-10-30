"""Price-quality sensitivity: repeat the market-based results of Steps 2, 3 and 5 under quote filters and de-vig methods (2025 sample).
Filters: none, spread (<= 0.05 on both sides), volume (> 0 in the used candle on at least one side), both. De-vig: proportional, power, Shin.
Ladders and props have single-contract prices, so de-vig applies to winners only. Gate: rehearsals 2, 3 and 5 passed."""
from scipy.optimize import brentq
from steps import *

for s_ in ("2", "3", "5"):
    gate(f"rehearsal_step{s_}.json")

hist = pd.read_parquet(HW / "kalshi_history.parquet")
hist = hist[hist.gid.str[:4] == "2025"]
BY = {g: d.sort_values("ts") for g, d in hist.groupby("gid")}


def devig(h, a, method):
    if method == "proportional":
        return h / (h + a)
    if method == "power":
        f = lambda k: h ** k + a ** k - 1
        try:
            k = brentq(f, 0.05, 20)
        except ValueError:
            return h / (h + a)
        return h ** k
    B = h + a
    f = lambda z: sum((np.sqrt(z * z + 4 * (1 - z) * q * q / B) - z) / (2 * (1 - z)) for q in (h, a)) - 1
    try:
        z = brentq(f, 1e-9, 0.95)
    except ValueError:
        return h / (h + a)
    return (np.sqrt(z * z + 4 * (1 - z) * h * h / B) - z) / (2 * (1 - z))


def price(gid, cut, filt, method):
    d = BY.get(gid)
    if d is None:
        return np.nan
    ko = d.kickoff_utc.iloc[0]
    x = d[(d.ts <= min(cut, ko)) & d.mid.notna()]
    if x.empty:
        return np.nan
    last = x.groupby("side").tail(1).set_index("side")
    if not {"home", "away"} <= set(last.index):
        return np.nan
    if filt in ("spread", "both") and ((last.ask - last.bid) > 0.05).any():
        return np.nan
    if filt in ("volume", "both") and not (last.volume > 0).any():
        return np.nan
    return float(devig(last.at["home", "mid"], last.at["away", "mid"], method))


def signature(ds):
    out = {}
    c = step2_ceilings(ds)
    out["winners_gap_includes_0"] = bool(c["winners"]["gap"]["lo"] <= 0 <= c["winners"]["gap"]["hi"])
    out["winners_mz_slope_includes_1"] = bool(c["winners"]["calibration"]["slope_ci"][0] <= 1 <= c["winners"]["calibration"]["slope_ci"][1])
    for t in ("margin", "total"):
        out[f"{t}_gap_includes_0"] = bool(c["ladders"][t]["gap_points"]["lo"] <= 0 <= c["ladders"][t]["gap_points"]["hi"])
    out["props_gap_includes_0"] = bool(c["props"]["gap"]["lo"] <= 0 <= c["props"]["gap"]["hi"])
    r5 = step5(ds, np.random.default_rng(SEED))
    out["winners_any_variant_p_wild_lt_0.05"] = bool(any(v["encompassing"]["p_wild"] < 0.05 for v in r5["winners"]["variants"].values()))
    out["winners_equivalence"] = {v: r5["winners"]["variants"][v]["equivalence"]["status"] for v in ("p_elo", "p_xgb_v1", "p_xgb_deep", "p_margin")}
    out["margin_L_p_wild_lt_0.05"] = bool(r5["ladders"]["margin"]["variants"]["L"]["encompassing"]["p_wild"] < 0.05)
    out["ladder_equivalence"] = {f"{t}_{v}": r5["ladders"][t]["variants"][v]["equivalence"]["status"] for t in ("margin", "total") for v in r5["ladders"][t]["variants"]}
    out["props_any_arm_p_wild_lt_0.05"] = bool(any(v["encompassing"]["p_wild"] < 0.05 for v in r5["props"].values()))
    out["props_equivalence"] = {a: v["equivalence"]["status"] for a, v in r5["props"].items()}
    try:
        r3 = step3(ds)
        out["news_term_includes_0"] = bool(r3["news_term_market_decision_minus_close"]["lo"] <= 0 <= r3["news_term_market_decision_minus_close"]["hi"])
        out["xgb_deep_vs_market_at_decision_includes_0"] = bool(r3["variants"]["p_xgb_deep"]["vs_market_at_decision"]["lo"] <= 0 <= r3["variants"]["p_xgb_deep"]["vs_market_at_decision"]["hi"])
        out["step3_games"] = r3["n_complete"]
    except Exception as e:
        out["step3_error"] = str(e)
    out["winners_games"] = int(len(ds["winners"]))
    return out


res = header("sensitivity")
base_ds = real_dataset(2025, "none")
Wb = base_ds["winners"]
W_dec = Wb.set_index("gid").decision_utc
# reproduce the base prices with the new price function (proves the rebuilt prices match the main run)
chk = [abs(price(g, pd.Timestamp(W_dec[g]), "none", "proportional") - Wb.set_index("gid").at[g, "p_dec"]) for g in Wb.gid[:60]]
res["base_price_reproduction_max_abs_error_first60"] = float(np.nanmax(chk))
sigs, counts = {}, {}
for filt in ("none", "spread", "volume", "both"):
    ds_f = real_dataset(2025, filt)
    for method in ("proportional", "power", "shin"):
        W = ds_f["winners"].copy()
        ko = hist.groupby("gid").kickoff_utc.first()
        for col, f in (("p_dec", lambda g: pd.Timestamp(W_dec[g])), ("p_t90", lambda g: ko[g] - LEAD), ("p_close", lambda g: ko[g])):
            W[col] = [price(g, f(g), filt, method) for g in W.gid]
        counts[f"{filt}|{method}"] = {"winners_with_t90_price": int(W.p_t90.notna().sum()), "margin_ladders": int((ds_f['ladders'].target == 'margin').sum()),
                                      "total_ladders": int((ds_f['ladders'].target == 'total').sum()), "props_ladders": int(len(ds_f['props_lad']))}
        ds_m = dict(ds_f); ds_m["winners"] = W[W.p_t90.notna()].reset_index(drop=True)
        if method != "proportional" and filt != "none":
            pass
        sigs[f"{filt}|{method}"] = signature(ds_m)
base = sigs["none|proportional"]
flips = {}
for k_, sg in sigs.items():
    d = {n: {"base": base[n], "this": sg[n]} for n in sg if n in base and sg[n] != base[n] and n not in ("winners_games", "step3_games")}
    if d:
        flips[k_] = d
res["counts"] = counts
res["signatures"] = sigs
res["conclusions_that_differ_from_base"] = flips
res["conclusion_flips"] = bool(flips)
write("sensitivity.json", res)
print("base reproduction error", res["base_price_reproduction_max_abs_error_first60"]); print("combos", len(sigs)); print("flips:", json.dumps(flips, indent=1)[:3000] if flips else "none")
print(counts["none|proportional"], counts["both|shin"])
