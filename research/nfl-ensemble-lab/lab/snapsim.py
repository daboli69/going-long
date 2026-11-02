"""Snap-by-snap game simulator. Every simulated game advances one snap at a time as a vector (docs/SNAPSIM_PREREG.md). Independent of the betting market."""
from __future__ import annotations

import numpy as np

from .snapfit import GAPS, Params, feats, hurry_state

LOGIT = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))
SIG = lambda x: 1.0 / (1.0 + np.exp(-x))


def _draw(arr: np.ndarray, rng, n: int) -> np.ndarray:
    return arr[rng.integers(0, len(arr), n)]


def _elapsed(P: Params, cat: str, hs: np.ndarray, pace: np.ndarray | None, rng) -> np.ndarray:
    out = np.zeros(len(hs))
    for h in (0, 1, 2):
        m = hs == h
        if not m.any():
            continue
        arr = P.elapsed.get((cat, h))
        if arr is None or len(arr) < 20:
            arr = P.elapsed.get((cat, 0))
        v = _draw(arr, rng, int(m.sum()))
        if h == 0 and pace is not None:
            v = v * pace[m]
        out[m] = v
    return out


def _pick(cum: np.ndarray, u: np.ndarray, zone: np.ndarray, sims: np.ndarray) -> np.ndarray:
    c = cum[zone] if cum.ndim == 2 else cum[sims, zone]
    return np.minimum((u[:, None] > c).sum(1), c.shape[1] - 1)


def simulate(P: Params, away: str, home: str, pools: dict, n: int = 10000, seed: int = 0, crowd_mult: float = 1.0, ot_sudden_death: bool = True) -> dict:
    """pools[0] is the away team, pools[1] the home team. Each: names, qb (index), tshare, cshare (zone x player, or sims x zone x player), catch (player logit), ypr (player yards per reception delta), rush_mult (sims x player or player)."""
    rng = np.random.default_rng(seed)
    T = (away, home)
    L = P.league
    S = n
    g = lambda d, key, t, default=0.0: d[key].get(t, default)
    arr = lambda d, key, default=0.0: np.array([g(d, key, T[0], default), g(d, key, T[1], default)])
    pass_delta, go_delta, pace = arr(P.off, "pass_delta"), arr(P.off, "go_delta"), arr(P.off, "pace", 1.0)
    pr_off, pr_def = arr(P.off, "pr", 1.0), arr(P.deff, "pr", 1.0)
    comp_off, comp_def = arr(P.off, "comp"), arr(P.deff, "comp")
    ypc_off, ypc_def = arr(P.off, "ypc"), arr(P.deff, "ypc")
    int_off, int_def = arr(P.off, "int", 1.0), arr(P.deff, "int", 1.0)
    ypr_off, ypr_def = arr(P.off, "ypr"), arr(P.deff, "ypr")
    fum_off = arr(P.off, "fum", 1.0)
    blitz = arr(P.deff, "blitz", L["blitz"])
    r_pre_off, r_live_off = arr(P.off, "pre_off", L["rate_pre_off"]), arr(P.off, "live_off", L["rate_live_off"])
    r_pre_def, r_live_def = arr(P.deff, "pre_def", L["rate_pre_def"]), arr(P.deff, "live_def", L["rate_live_def"])
    r_pre_off = r_pre_off * np.array([crowd_mult, 1.0])          # away offense is the visitor
    gap_cum = [np.cumsum(P.off["gap_mix"].get(t, np.full(7, 1 / 7)))for t in T]
    pc, pi = P.pass_coef
    c4, i4 = P.fourth_coef
    fgc, fgi = P.fg_coef

    score = np.zeros((S, 2), dtype=int)
    first = rng.integers(0, 2, S)
    poss = first.copy()
    yl = _draw(P.ko_start, rng, S).copy()
    down = np.ones(S, dtype=int)
    ytg = np.full(S, 10)
    gsr = np.full(S, 3600.0)
    done = np.zeros(S, dtype=bool)
    ot = np.zeros(S, dtype=bool)
    st = {k: np.zeros((S, 2), dtype=int) for k in ("snaps", "dropbacks", "sacks", "penalties", "fourth_go", "tds", "fgs", "ints", "fumbles", "false_starts", "pass_att", "rush_att", "punts", "fg_att")}
    np_ = [len(p["names"]) for p in pools]
    acc = [{k: np.zeros((S, np_[t])) for k in ("tgt", "rec", "recyd", "car", "rushyd", "rectd", "rushtd")} for t in (0, 1)]
    qbacc = [{k: np.zeros(S) for k in ("att", "comp", "yds", "td", "int", "sacks")} for t in (0, 1)]

    def kickoff_to(sims, team):
        poss[sims] = team
        yl[sims] = _draw(P.ko_start, rng, len(sims))
        down[sims] = 1
        ytg[sims] = 10

    def clock(sims, cat, o_, hs_):
        gsr[sims] -= _elapsed(P, cat, hs_, pace[o_], rng)

    for it in range(450):
        idx = np.flatnonzero(~done)
        if not len(idx):
            break
        n_ = len(idx)
        o = poss[idx]
        d = 1 - o
        dn, yt, y0, gs = down[idx], ytg[idx], yl[idx], gsr[idx]
        sd = score[idx, o] - score[idx, d]
        hsr = np.where(gs > 1800, gs - 1800, gs)
        qtr = np.minimum(4, 1 + ((3600 - np.clip(gs, 0, 3600)) // 900)).astype(int)
        hs = np.where(ot[idx], 0, hurry_state(sd, gs, hsr, qtr))
        gs_before = gs.copy()
        fx = feats(dn, yt, y0, sd, np.where(ot[idx], 900.0, gs))
        acted = np.zeros(n_, dtype=bool)      # sims whose snap is fully handled

        # ---- fourth down decision
        kick = np.zeros(n_, dtype=bool)
        is4 = dn == 4
        if is4.any():
            lg = fx[is4] @ c4.T + i4
            lg[:, 0] += go_delta[o[is4]]
            pr = np.exp(lg - lg.max(1, keepdims=True))
            pr /= pr.sum(1, keepdims=True)
            u = rng.random(is4.sum())
            cls = (u[:, None] > pr.cumsum(1)).sum(1)
            cls = np.minimum(cls, 2)
            cls = np.where((cls == 1) & (y0[is4] > 60), 2, cls)
            kcls = np.full(n_, -1)
            kcls[np.flatnonzero(is4)] = cls
            kick = kcls >= 1
            st["fourth_go"][idx[is4 & (kcls == 0)], o[is4 & (kcls == 0)]] += 1
        # field goals
        fgm = kick & (kcls == 1) if is4.any() else np.zeros(n_, dtype=bool)
        if fgm.any():
            s = idx[fgm]
            pm = SIG(fgc * (y0[fgm] + 17) + fgi)
            made = rng.random(len(s)) < pm
            sc_ = s[made]
            score[sc_, o[fgm][made]] += 3
            st["fgs"][sc_, o[fgm][made]] += 1
            st["fg_att"][s, o[fgm]] += 1
            clock(s, "fg", o[fgm], hs[fgm])
            miss = s[~made]
            om = o[fgm][~made]
            opp = np.minimum(100 - (y0[fgm][~made] + 7), 80)
            poss[miss] = 1 - om
            yl[miss] = opp
            down[miss], ytg[miss] = 1, 10
            if len(sc_):
                gsr[sc_] -= _elapsed(P, "ko", np.zeros(len(sc_), dtype=int), None, rng)
                kickoff_to(sc_, 1 - o[fgm][made])
            acted |= fgm
        pnt = kick & (kcls == 2) if is4.any() else np.zeros(n_, dtype=bool)
        if pnt.any():
            s = idx[pnt]
            net = _draw(P.yards["punt"], rng, len(s))
            rem = y0[pnt] - net
            opp = np.where(rem <= 0, 80, np.minimum(100 - rem, 99))
            st["punts"][s, o[pnt]] += 1
            clock(s, "punt", o[pnt], hs[pnt])
            poss[s] = 1 - o[pnt]
            yl[s] = opp
            down[s], ytg[s] = 1, 10
            acted |= pnt

        # ---- pre-snap and live penalties
        go = ~acted
        pre_o = r_pre_off[o] * go
        pre_d = r_pre_def[d] * go
        liv_o = r_live_off[o] * go
        liv_d = r_live_def[d] * go
        u = rng.random(n_)
        cum = np.cumsum(np.column_stack([pre_o, pre_d, liv_o, liv_d]), axis=1)
        ev = np.where(go, (u[:, None] > cum).sum(1), 4)      # 0..3 penalty classes, 4 none
        for k, (cat_key, sgn) in enumerate((("pre_off", 1), ("pre_def", -1), ("live_off", 1), ("live_def", -1))):
            m = ev == k
            if not m.any():
                continue
            s = idx[m]
            yd = L["pyds_" + cat_key]
            if k in (0, 2):
                yl[s] = np.minimum(y0[m] + yd, 99)
                ytg[s] = yt[m] + yd
            elif k == 1:
                yl[s] = np.maximum(y0[m] - yd, 1)
                ytg[s] = yt[m] - yd
                fd = ytg[s] <= 0
                down[s[fd]] = 1
                ytg[s[fd]] = np.minimum(10, yl[s[fd]])
            else:
                yl[s] = np.maximum(y0[m] - yd, 1)
                down[s], ytg[s] = 1, np.minimum(10, yl[s])
            st["penalties"][s, o[m] if k in (0, 2) else d[m]] += 1
            if k == 0:
                st["false_starts"][s, o[m]] += 1
            clock(s, "pen", o[m], hs[m])
            acted |= m

        # ---- the snap
        pl = ~acted
        if pl.any():
            pi_ = np.flatnonzero(pl)
            s = idx[pi_]
            m_ = len(s)
            oo, dd = o[pi_], d[pi_]
            lgp = fx[pi_] @ pc + pi + pass_delta[oo]
            is_pass = rng.random(m_) < SIG(lgp)
            yg = np.zeros(m_)
            turn = np.zeros(m_, dtype=bool)
            tdm = np.zeros(m_, dtype=bool)
            spot_turn = np.zeros(m_)
            cat = np.full(m_, "run", dtype=object)
            st["snaps"][s, oo] += 1
            zone = (y0[pi_] <= 10).astype(int)
            # pass
            pp = np.flatnonzero(is_pass)
            if len(pp):
                sp = s[pp]
                o2, d2 = oo[pp], dd[pp]
                st["dropbacks"][sp, o2] += 1
                b = rng.random(len(pp)) < blitz[d2]
                ppr = np.where(b, L["pr_b1"], L["pr_b0"]) * pr_off[o2] * pr_def[d2]
                pres = rng.random(len(pp)) < np.clip(ppr, 0.02, 0.7)
                sack = pres & (rng.random(len(pp)) < L["pr_sack"])
                scr = ~pres & (rng.random(len(pp)) < L["scr"] / (1 - L["pr"]))
                att = ~sack & ~scr
                yy = np.zeros(len(pp))
                if sack.any():
                    yy[sack] = _draw(P.yards["sack"], rng, int(sack.sum()))
                    st["sacks"][sp[sack], o2[sack]] += 1
                    fl = rng.random(int(sack.sum())) < L["fum_sack"]
                    tt = np.flatnonzero(sack)[fl]
                    turn[pp[tt]] = True
                    spot_turn[pp[tt]] = y0[pi_][pp[tt]] - yy[tt]
                    for t_ in (0, 1):
                        mm = sack & (o2 == t_)
                        np.add.at(qbacc[t_]["sacks"], sp[mm], 1)
                    cat[pp[sack]] = "sack"
                if scr.any():
                    yy[scr] = _draw(P.yards["scramble"], rng, int(scr.sum()))
                    for t_ in (0, 1):
                        mm = scr & (o2 == t_)
                        if mm.any():
                            q = pools[t_]["qb"]
                            np.add.at(acc[t_]["car"], (sp[mm], np.full(int(mm.sum()), q)), 1)
                            np.add.at(acc[t_]["rushyd"], (sp[mm], np.full(int(mm.sum()), q)), 0)   # yards added below
                aa = np.flatnonzero(att)
                if len(aa):
                    sa = sp[aa]
                    oa, da = o2[aa], d2[aa]
                    st["pass_att"][sa, oa] += 1
                    tgt = np.zeros(len(aa), dtype=int)
                    for t_ in (0, 1):
                        mm = oa == t_
                        if mm.any():
                            tgt[mm] = _pick(pools[t_]["tcum"], rng.random(int(mm.sum())), zone[pp][aa][mm], sa[mm])
                    base = np.where(pres[aa], L["comp_pr1"], L["comp_pr0"])
                    cdelta = np.zeros(len(aa))
                    ydelta = np.zeros(len(aa))
                    for t_ in (0, 1):
                        mm = oa == t_
                        cdelta[mm] = pools[t_]["catch"][tgt[mm]]
                        ydelta[mm] = pools[t_]["ypr"][tgt[mm]]
                    pc_ = SIG(LOGIT(base) + comp_off[oa] + comp_def[da] + cdelta)
                    pint = np.clip(np.where(pres[aa], L["int_pr1"], L["int_pr0"]) * int_off[oa] * int_def[da], 0.002, 0.2)
                    ui = rng.random(len(aa))
                    isint = ui < pint
                    comp = ~isint & (rng.random(len(aa)) < pc_)
                    ya = _draw(P.yards["comp"], rng, len(aa)) + ypc_off[oa] + ypc_def[da] + ydelta
                    ya = np.where(comp, np.clip(np.round(ya), -3, None), 0.0)
                    yy[aa] = ya
                    cat[pp[aa]] = np.where(comp, "comp", "inc")
                    fl = comp & (rng.random(len(aa)) < L["fum_pass"])
                    isint_g = pp[aa][isint]
                    turn[isint_g] = True
                    spot_turn[isint_g] = np.maximum(y0[pi_][isint_g] - 10, 1)
                    turn[pp[aa][fl]] = True
                    spot_turn[pp[aa][fl]] = y0[pi_][pp[aa][fl]] - ya[fl]
                    for t_ in (0, 1):
                        mm = oa == t_
                        if not mm.any():
                            continue
                        np.add.at(acc[t_]["tgt"], (sa[mm], tgt[mm]), 1)
                        np.add.at(qbacc[t_]["att"], sa[mm], 1)
                        np.add.at(qbacc[t_]["int"], sa[mm & isint], 1)
                        cm = mm & comp
                        np.add.at(acc[t_]["rec"], (sa[cm], tgt[cm]), 1)
                        np.add.at(acc[t_]["recyd"], (sa[cm], tgt[cm]), np.minimum(ya[cm], y0[pi_][pp[aa]][cm]))
                        np.add.at(qbacc[t_]["comp"], sa[cm], 1)
                        np.add.at(qbacc[t_]["yds"], sa[cm], np.minimum(ya[cm], y0[pi_][pp[aa]][cm]))
                    st["ints"][sa[isint], oa[isint]] += 1
                yg[pp] = yy
                tdp = (yy >= y0[pi_][pp]) & ~turn[pp]
                tdm[pp] = tdp
                # touchdown credit to the receiver and the passer
                for t_ in (0, 1):
                    mm = tdp[:len(pp)] & (o2 == t_) & att
                    if mm.any():
                        a_idx = np.flatnonzero(mm)
                        np.add.at(qbacc[t_]["td"], sp[a_idx], 1)
                        # receiver of this attempt
                        pos = {int(v): k for k, v in enumerate(aa)}
                        tt = np.array([tgt[pos[int(v)]] for v in a_idx])
                        np.add.at(acc[t_]["rectd"], (sp[a_idx], tt), 1)
            # run
            rr = np.flatnonzero(~is_pass)
            if len(rr):
                sr = s[rr]
                o2, d2 = oo[rr], dd[rr]
                st["rush_att"][sr, o2] += 1
                ur = rng.random(len(rr))
                cat_i = np.zeros(len(rr), dtype=int)
                for t_ in (0, 1):
                    mm = o2 == t_
                    cat_i[mm] = np.minimum((ur[mm, None] > gap_cum[t_][None, :]).sum(1), 6)
                yy = np.zeros(len(rr))
                for k, name in enumerate(GAPS):
                    mm = cat_i == k
                    if mm.any():
                        yy[mm] = _draw(P.yards["run_" + name], rng, int(mm.sum()))
                car = np.zeros(len(rr), dtype=int)
                mult = np.ones(len(rr))
                dlt = np.zeros(len(rr))
                for t_ in (0, 1):
                    mm = o2 == t_
                    if mm.any():
                        car[mm] = _pick(pools[t_]["ccum"], rng.random(int(mm.sum())), zone[rr][mm], sr[mm])
                        rm = pools[t_]["rush_mult"]
                        mult[mm] = (rm[sr[mm], car[mm]] if rm.ndim == 2 else rm[car[mm]])
                        dlt[mm] = pools[t_]["ypc"][car[mm]]
                yy = np.round((yy + ypr_off[o2] + ypr_def[d2] + dlt) * mult)
                fl = rng.random(len(rr)) < (L["fum_run"] * fum_off[o2])
                turn[rr[fl]] = True
                spot_turn[rr[fl]] = y0[pi_][rr[fl]] - yy[fl]
                tdr = (yy >= y0[pi_][rr]) & ~fl
                tdm[rr] = tdr
                yg[rr] = yy
                for t_ in (0, 1):
                    mm = o2 == t_
                    if mm.any():
                        yc = np.minimum(yy, y0[pi_][rr])
                        np.add.at(acc[t_]["car"], (sr[mm], car[mm]), 1)
                        np.add.at(acc[t_]["rushyd"], (sr[mm], car[mm]), yc[mm])
                        mt = mm & tdr
                        np.add.at(acc[t_]["rushtd"], (sr[mt], car[mt]), 1)
            # scramble yards go to the quarterback
            if len(pp):
                scm = np.zeros(m_, dtype=bool)
                scm[pp[scr]] = True if scr.any() else False
                for t_ in (0, 1):
                    mm = scm & (oo == t_)
                    if mm.any():
                        np.add.at(acc[t_]["rushyd"], (s[mm], np.full(int(mm.sum()), pools[t_]["qb"])), np.minimum(yg[mm], y0[pi_][mm]))
                        tq = mm & tdm
                        np.add.at(acc[t_]["rushtd"], (s[tq], np.full(int(tq.sum()), pools[t_]["qb"])), 1)
                cat[scm] = "run"
            yg = np.minimum(yg, y0[pi_])
            # ---- apply the result
            y_old, dn_old, yt_old = y0[pi_], dn[pi_], yt[pi_]
            new_yl = y_old - yg
            fd = (yg >= yt_old) & ~turn
            nd = np.where(fd, 1, dn_old + 1)
            nyt = np.where(fd, np.minimum(10, np.maximum(new_yl, 1)), yt_old - yg)
            tod = (~fd) & (dn_old == 4) & ~turn & ~tdm
            flip = turn | tod
            opp_yl = np.where(turn, np.minimum(100 - np.maximum(spot_turn, 1), 99), np.minimum(100 - new_yl, 99))
            normal = ~flip & ~tdm
            yl[s[normal]] = new_yl[normal]
            down[s[normal]] = nd[normal]
            ytg[s[normal]] = nyt[normal]
            poss[s[flip]] = 1 - oo[flip]
            yl[s[flip]] = opp_yl[flip]
            down[s[flip]], ytg[s[flip]] = 1, 10
            cat = np.where(tdm, "td", cat)
            for c_ in ("run", "comp", "inc", "sack", "td"):
                mm = cat == c_
                if mm.any():
                    gsr[s[mm]] -= _elapsed(P, c_, hs[pi_][mm], pace[oo[mm]], rng)
            # scores
            if tdm.any():
                st_ = s[tdm]
                ot_ = oo[tdm]
                xp = rng.random(len(st_)) < L["xp"]
                score[st_, ot_] += 6 + xp.astype(int)
                st["tds"][st_, ot_] += 1
                gsr[st_] -= _elapsed(P, "ko", np.zeros(len(st_), dtype=int), None, rng)
                kickoff_to(st_, 1 - ot_)
        # ---- halftime, end of regulation, overtime
        g2 = gsr[idx]
        cross = (gs_before > 1800) & (g2 <= 1800) & ~ot[idx]
        if cross.any():
            s = idx[cross]
            gsr[s] = 1800.0
            kickoff_to(s, 1 - first[s])
        end = (gsr[idx] <= 0) & ~ot[idx]
        if end.any():
            s = idx[end]
            tie = score[s, 0] == score[s, 1]
            done[s[~tie]] = True
            tt = s[tie]
            if len(tt):
                ot[tt] = True
                gsr[tt] = 600.0
                kickoff_to(tt, rng.integers(0, 2, len(tt)))
                st["tds"][tt, 0] += 0
        # overtime resolution below
        if ot.any():
            oi = np.flatnonzero(ot & ~done)
            if len(oi):
                diff = score[oi, 0] != score[oi, 1]
                done[oi[diff]] = True
                done[oi[gsr[oi] <= 0]] = True
    return {"score": score, "stats": st, "acc": acc, "qb": qbacc, "teams": T}
