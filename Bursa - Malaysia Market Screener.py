# ============================================================
# BULLISH SCREENER — Flask Web Dashboard
# File  : Bursa - Malaysia Market Screener.py
# Run   : python "Bursa - Malaysia Market Screener.py"
# Open  : http://localhost:5000
# ============================================================

from flask import Flask, jsonify
from tradingview_screener import Query, col
import pandas as pd
from datetime import datetime
import traceback

# ── FLASK SETUP ──────────────────────────────────────────────
app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    return response

# ── CONFIG ───────────────────────────────────────────────────
# ✅ KEY mesti konsisten — guna key ini untuk .get() juga
TIMEFRAMES = {
    "Monthly_1M"      : "1M",
    "Weekly_1W"       : "1W",
    "Daily_1D"        : "1D",
    "4Hour_4H"        : "240",
    "1Hour_1H"        : "60",
    "15Minutes_15min" : "15",
    "5Minutes_5min"   : "5",
}

# ════════════════════════════════════════════════════════════
# ELLIOTT WAVE + PRICE SUGGESTION
# ════════════════════════════════════════════════════════════
def elliott_wave_analysis(row):
    try:
        price    = safe_float(row.get("Price",    0))
        high_52w = safe_float(row.get("High_52W", 0))
        low_52w  = safe_float(row.get("Low_52W",  0))
        ema20    = safe_float(row.get("EMA20",     0))
        ema50    = safe_float(row.get("EMA50",     0))
        ema200   = safe_float(row.get("EMA200",    0))
        rsi      = safe_float(row.get("RSI",       50))
        macd     = safe_float(row.get("MACD",      0))
        macd_sig = safe_float(row.get("MACD_Sig",  0))
        volume   = safe_float(row.get("Volume",    0))
        avg_vol  = safe_float(row.get("Avg_Vol",   1))

        if any(pd.isna(v) for v in [price, high_52w, low_52w]):
            return {
                "wave"       : "N/A",
                "wave_desc"  : "Data tidak cukup",
                "buy_price"  : 0,
                "sell_price" : 0,
                "stop_loss"  : 0,
                "direction"  : "NEUTRAL",
                "confidence" : 0,
                "rr_ratio"   : 0,
            }

        total_range = high_52w - low_52w
        if total_range <= 0:
            total_range = price * 0.1

        fib_382  = low_52w + total_range * 0.382
        fib_500  = low_52w + total_range * 0.500
        fib_618  = low_52w + total_range * 0.618
        ext_1272 = high_52w + total_range * 0.272
        ext_1618 = high_52w + total_range * 0.618

        pos_pct   = (price - low_52w) / total_range * 100
        vol_ratio = volume / avg_vol if avg_vol > 0 else 1

        score_up   = 0
        score_down = 0

        if not any(pd.isna(v) for v in [ema20, ema50, ema200]):
            if ema20 > ema50 > ema200:    score_up   += 3
            elif ema20 > ema50:           score_up   += 2
            elif ema20 < ema50 < ema200:  score_down += 3

        if not pd.isna(ema20):
            if price > ema20:  score_up   += 2
            else:              score_down += 2

        if not pd.isna(rsi):
            if 50 <= rsi <= 70:   score_up   += 3
            elif rsi > 70:        score_down += 1
            elif 30 <= rsi < 50:  score_down += 2
            elif rsi < 30:        score_up   += 1

        if not any(pd.isna(v) for v in [macd, macd_sig]):
            if macd > macd_sig and macd > 0:  score_up   += 3
            elif macd > macd_sig:             score_up   += 2
            elif macd < macd_sig:             score_down += 2

        if pos_pct >= 80:    score_down += 1
        elif pos_pct >= 50:  score_up   += 2
        elif pos_pct >= 30:  score_up   += 1
        else:                score_down += 1

        if vol_ratio >= 1.5:   score_up   += 2
        elif vol_ratio < 0.8:  score_down += 1

        total_score = score_up + score_down
        bull_pct    = score_up / total_score * 100 if total_score > 0 else 50

        if bull_pct >= 75:
            if pos_pct >= 60:
                wave      = "Wave 3"
                wave_desc = "Impulse Wave 3 — Paling kuat & panjang"
                direction = "STRONG UP ⬆️⬆️"
            else:
                wave      = "Wave 1"
                wave_desc = "Impulse Wave 1 — Permulaan trend naik"
                direction = "UP ⬆️"
        elif bull_pct >= 60:
            if pos_pct >= 70:
                wave      = "Wave 5"
                wave_desc = "Impulse Wave 5 — Akhir trend naik, berhati-hati"
                direction = "UP ⬆️ (Caution)"
            else:
                wave      = "Wave 3"
                wave_desc = "Impulse Wave 3 — Momentum kuat"
                direction = "UP ⬆️"
        elif bull_pct >= 45:
            if pos_pct <= 40:
                wave      = "Wave 2"
                wave_desc = "Corrective Wave 2 — Pullback, peluang beli"
                direction = "PULLBACK ↘️ (Buy Dip)"
            else:
                wave      = "Wave 4"
                wave_desc = "Corrective Wave 4 — Konsolidasi, tunggu Wave 5"
                direction = "SIDEWAYS ↔️"
        else:
            wave      = "Wave A/B/C"
            wave_desc = "Corrective ABC — Trend turun sementara"
            direction = "DOWN ⬇️"

        if "Wave 1" in wave or "Wave 3" in wave:
            buy_price  = round(fib_618 if price > fib_618 else
                               fib_500 if price > fib_500 else
                               price * 0.98, 3)
            stop_loss  = round(buy_price * 0.95, 3)
            sell_price = round(ext_1618 if "Wave 3" in wave
                               else high_52w * 1.05, 3)
        elif "Wave 5" in wave:
            buy_price  = round(price * 0.99, 3)
            stop_loss  = round(fib_618, 3)
            sell_price = round(ext_1272, 3)
        elif "Wave 2" in wave:
            buy_price  = round(fib_618, 3)
            stop_loss  = round(low_52w * 1.01, 3)
            sell_price = round(ext_1618, 3)
        elif "Wave 4" in wave:
            buy_price  = round(fib_382, 3)
            stop_loss  = round(fib_500, 3)
            sell_price = round(ext_1272, 3)
        else:
            buy_price  = round(low_52w * 1.02, 3)
            stop_loss  = round(low_52w * 0.97, 3)
            sell_price = round(fib_382, 3)

        risk       = abs(price - stop_loss)
        reward     = abs(sell_price - price)
        rr         = round(reward / risk, 2) if risk > 0 else 0
        confidence = round(
            bull_pct if "UP" in direction else (100 - bull_pct), 1
        )

        return {
            "wave"       : wave,
            "wave_desc"  : wave_desc,
            "buy_price"  : buy_price,
            "sell_price" : sell_price,
            "stop_loss"  : stop_loss,
            "direction"  : direction,
            "confidence" : confidence,
            "rr_ratio"   : rr,
            "fib_382"    : round(fib_382, 3),
            "fib_618"    : round(fib_618, 3),
        }

    except Exception as e:
        return {
            "wave"       : "ERR",
            "wave_desc"  : str(e),
            "buy_price"  : 0,
            "sell_price" : 0,
            "stop_loss"  : 0,
            "direction"  : "N/A",
            "confidence" : 0,
            "rr_ratio"   : 0,
        }


def market_direction(data_list):
    if not data_list:
        return "NEUTRAL", 0
    up_count = sum(1 for r in data_list if "UP" in r.get("direction", ""))
    total    = len(data_list)
    up_pct   = up_count / total * 100
    if up_pct >= 70:   return "🟢 BULLISH MARKET",  round(up_pct, 1)
    elif up_pct >= 55: return "🟡 MILD BULLISH",     round(up_pct, 1)
    elif up_pct >= 45: return "⚪ NEUTRAL/SIDEWAYS", round(up_pct, 1)
    elif up_pct >= 30: return "🟠 MILD BEARISH",     round(up_pct, 1)
    else:              return "🔴 BEARISH MARKET",   round(up_pct, 1)


# ════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ════════════════════════════════════════════════════════════
def safe_float(val):
    try:
        v = float(val)
        return v if not pd.isna(v) else float("nan")
    except:
        return float("nan")

def rating_label(val):
    v = safe_float(val)
    if pd.isna(v):  return "N/A"
    if v >= 0.5:    return "Strong Buy"
    if v >= 0.1:    return "Buy"
    if v > -0.1:    return "Neutral"
    if v > -0.5:    return "Sell"
    return "Strong Sell"

def rsi_zone(val):
    v = safe_float(val)
    if pd.isna(v):       return "N/A"
    if v >= 80:          return "Extreme OB"
    if v >= 70:          return "Overbought"
    if 55 <= v < 70:     return "Sweet Spot"
    if 50 <= v < 55:     return "Bullish"
    if 30 <= v < 50:     return "Bearish"
    return "Oversold"

def macd_label(macd, sig):
    m = safe_float(macd)
    s = safe_float(sig)
    if pd.isna(m) or pd.isna(s): return "N/A"
    if m > s and m > 0:           return "Bull+Zero"
    if m > s and m <= 0:          return "Bull-Zero"
    if m <= s and m > 0:          return "Bear+Zero"
    return "Bear-Zero"

def ema_trend(e20, e50, e200):
    a = safe_float(e20)
    b = safe_float(e50)
    c = safe_float(e200)
    if pd.isna(a) or pd.isna(b) or pd.isna(c): return "N/A"
    if a > b > c:  return "Perfect Bull"
    if a > b:      return "Partial Bull"
    if a < b < c:  return "Perfect Bear"
    return "Mixed"

def score_stock(row):
    score = 0
    et = row.get("EMA_Trend", "")
    if et == "Perfect Bull":   score += 15
    elif et == "Partial Bull": score += 8

    rz = row.get("RSI_Zone", "")
    if rz == "Sweet Spot":     score += 10
    elif rz == "Bullish":      score += 6

    ml = row.get("MACD_Label", "")
    if ml == "Bull+Zero":      score += 10
    elif ml == "Bull-Zero":    score += 6

    ts = row.get("Tech_Signal", "")
    if ts == "Strong Buy":     score += 8
    elif ts == "Buy":          score += 4

    roe = safe_float(row.get("ROE", 0))
    if not pd.isna(roe):
        if roe >= 20:   score += 10
        elif roe >= 15: score += 8
        elif roe >= 10: score += 5
        elif roe >= 5:  score += 2

    nm = safe_float(row.get("Net_Margin", 0))
    if not pd.isna(nm):
        if nm >= 20:    score += 8
        elif nm >= 10:  score += 6
        elif nm >= 5:   score += 3

    pe = safe_float(row.get("PE", 0))
    if not pd.isna(pe) and pe > 0:
        if pe <= 10:    score += 7
        elif pe <= 15:  score += 6
        elif pe <= 20:  score += 4

    rg = safe_float(row.get("Rev_Growth", 0))
    if not pd.isna(rg):
        if rg >= 20:    score += 7
        elif rg >= 10:  score += 5
        elif rg >= 0:   score += 2

    de = safe_float(row.get("DE_Ratio", 999))
    if not pd.isna(de):
        if de <= 0.3:   score += 5
        elif de <= 0.5: score += 4
        elif de <= 1.0: score += 2

    return min(score, 100)

def score_grade(score):
    if score >= 85:  return "A+"
    if score >= 75:  return "A"
    if score >= 65:  return "B+"
    if score >= 55:  return "B"
    if score >= 45:  return "C"
    return "D"
# ════════════════════════════════════════════════════════════
# TRADER PRO SIGNAL
# ════════════════════════════════════════════════════════════
def trader_pro_signal(row):
    price      = safe_float(row.get("Price",      0))
    buy_price  = safe_float(row.get("Buy_Price",  0))
    sl_price   = safe_float(row.get("Stop_Loss",  0))
    rsi        = safe_float(row.get("RSI",        0))
    volume     = safe_float(row.get("Volume",     0))
    avg_vol    = safe_float(row.get("Avg_Vol",    1))
    wave       = row.get("EW_Wave",    "")
    ema_trend  = row.get("EMA_Trend",  "")
    macd_lbl   = row.get("MACD_Label", "")
    rr         = safe_float(row.get("RR_Ratio",   0))

    if price <= 0 or buy_price <= 0:
        return "N/A"

    diff_pct  = (price - buy_price) / buy_price * 100
    vol_ratio = volume / avg_vol if avg_vol > 0 else 1

    # ── Bahaya — bawah SL ────────────────────────────────
    if sl_price > 0 and price < sl_price:
        return "💀 ABORT"

    # ── Harga terlalu rendah ──────────────────────────────
    if diff_pct < -5:
        return "⬇️ OVERSOLD"

    # ── Confluence Score ──────────────────────────────────
    conf = 0

    # 1. EMA Trend
    if ema_trend == "Perfect Bull":   conf += 2
    elif ema_trend == "Partial Bull": conf += 1

    # 2. RSI Zone (55~65 = ideal pro)
    if 55 <= rsi <= 65:    conf += 2
    elif 50 <= rsi < 55:   conf += 1
    elif rsi > 68:         conf -= 1  # Terlalu tinggi

    # 3. Volume
    if vol_ratio >= 2.0:   conf += 2  # Institutional buying
    elif vol_ratio >= 1.5: conf += 1

    # 4. Wave Quality
    if wave == "Wave 3":    conf += 2  # Paling kuat
    elif wave == "Wave 1":  conf += 1
    elif wave == "Wave 2":  conf += 2  # Buy dip terbaik
    elif wave == "Wave 5":  conf -= 1  # Hampir habis

    # 5. MACD
    if macd_lbl == "Bull+Zero":  conf += 2
    elif macd_lbl == "Bull-Zero": conf += 1

    # 6. R:R
    if rr >= 3:    conf += 2
    elif rr >= 2:  conf += 1
    elif rr < 1.5: conf -= 1

    # ── Signal Output ─────────────────────────────────────
    if diff_pct <= 1 and conf >= 7:
        return "🎯 STRONG BUY"
    elif diff_pct <= 2 and conf >= 5:
        return "✅ BUY LIMIT"
    elif diff_pct <= 5 and conf >= 4:
        return "🔔 SET ALERT"
    elif diff_pct <= 15 and conf >= 4:
        return "⏳ WAIT PULL"
    elif diff_pct <= 15 and conf >= 2:
        return "👀 MONITOR"
    elif diff_pct > 15 and conf >= 5:
        return "📋 WATCHLIST"
    else:
        return "⏭️ SKIP"


# ════════════════════════════════════════════════════════════
# ROBOT ALGO SIGNAL — Standard sama dengan Trader Pro
# ════════════════════════════════════════════════════════════
def robot_algo_signal(row):
    """
    Robot Algo — guna ATR + Expected Value + Momentum
    Signal OUTPUT sama standard dengan Trader Pro:
    🎯 STRONG BUY / ✅ BUY LIMIT / 🔔 SET ALERT /
    ⏳ WAIT PULL  / 👀 MONITOR   / 📋 WATCHLIST /
    ⏭️ SKIP       / 💀 ABORT     / ⬇️ OVERSOLD
    """
    price      = safe_float(row.get("Price",      0))
    buy_price  = safe_float(row.get("Buy_Price",  0))
    sl_price   = safe_float(row.get("Stop_Loss",  0))
    high_52w   = safe_float(row.get("High_52W",   0))
    low_52w    = safe_float(row.get("Low_52W",    0))
    rsi        = safe_float(row.get("RSI",        0))
    volume     = safe_float(row.get("Volume",     0))
    avg_vol    = safe_float(row.get("Avg_Vol",    1))
    wave       = row.get("EW_Wave",    "")
    macd_lbl   = row.get("MACD_Label", "")
    score      = safe_float(row.get("Score",      0))
    rr         = safe_float(row.get("RR_Ratio",   0))

    if price <= 0 or buy_price <= 0 or high_52w <= 0:
        return "N/A"

    # ── ATR Estimation ────────────────────────────────────
    atr        = (high_52w - low_52w) / 52
    atr_sl     = buy_price - (1.5 * atr)
    atr_tp     = buy_price + (3.0 * atr)
    atr_risk   = buy_price - atr_sl   if atr_sl > 0 else 1
    atr_reward = atr_tp - buy_price
    atr_rr     = atr_reward / atr_risk if atr_risk > 0 else 0

    # ── Win Rate by Wave ──────────────────────────────────
    wr_map = {
        "Wave 3"    : 0.72,
        "Wave 1"    : 0.65,
        "Wave 2"    : 0.70,
        "Wave 5"    : 0.58,
        "Wave 4"    : 0.55,
        "Wave A/B/C": 0.35,
    }
    wr = wr_map.get(wave, 0.50)

    # ── Expected Value (EV) ───────────────────────────────
    ev = (wr * atr_reward) - ((1 - wr) * atr_risk)

    # ── Distance dari Buy Zone ────────────────────────────
    diff_pct  = (price - buy_price) / buy_price * 100
    vol_ratio = volume / avg_vol if avg_vol > 0 else 1

    # ── Momentum Score (sama konsep dengan Trader Pro) ────
    mom = 0

    # 1. RSI
    if 55 <= rsi <= 65:    mom += 2
    elif 50 <= rsi < 55:   mom += 1
    elif rsi > 68:         mom -= 1

    # 2. Volume
    if vol_ratio >= 2.0:   mom += 2
    elif vol_ratio >= 1.5: mom += 1

    # 3. MACD
    if macd_lbl == "Bull+Zero":   mom += 2
    elif macd_lbl == "Bull-Zero": mom += 1

    # 4. Score
    if score >= 75:   mom += 2
    elif score >= 60: mom += 1

    # 5. ATR R:R
    if atr_rr >= 3:   mom += 2
    elif atr_rr >= 2: mom += 1
    elif atr_rr < 1.5: mom -= 1

    # 6. Wave Quality
    if wave == "Wave 3":    mom += 2
    elif wave == "Wave 1":  mom += 1
    elif wave == "Wave 2":  mom += 2
    elif wave == "Wave 5":  mom -= 1

    # ── BAHAYA — Bawah SL ────────────────────────────────
    if sl_price > 0 and price < sl_price:
        return "💀 ABORT"

    # ── Harga terlalu rendah ──────────────────────────────
    if diff_pct < -5:
        return "⬇️ OVERSOLD"

    # ── EV Negatif — algo skip terus ─────────────────────
    if ev <= 0:
        return "⏭️ SKIP"

    # ── Signal Output — SAMA standard Trader Pro ─────────
    if diff_pct <= 1 and mom >= 7 and atr_rr >= 2:
        return "🎯 STRONG BUY"

    elif diff_pct <= 2 and mom >= 5 and atr_rr >= 1.5:
        return "✅ BUY LIMIT"

    elif diff_pct <= 5 and mom >= 4:
        return "🔔 SET ALERT"

    elif diff_pct <= 15 and mom >= 4:
        return "⏳ WAIT PULL"

    elif diff_pct <= 15 and mom >= 2:
        return "👀 MONITOR"

    elif diff_pct > 15 and mom >= 5:
        return "📋 WATCHLIST"

    else:
        return "⏭️ SKIP"

# ════════════════════════════════════════════════════════════
# FETCH FUNCTION — FILTER KETAT
# ════════════════════════════════════════════════════════════
def fetch_screener(tf):
    COLUMNS = [
        "name", "description", "sector",
        "market_cap_basic", "close",
        f"change|{tf}",
        f"volume|{tf}",
        "average_volume_10d_calc",
        "earnings_per_share_diluted_ttm",
        "price_earnings_ttm",
        "price_to_book_fwd",
        "dividends_yield_current",
        "return_on_equity",
        "return_on_assets",
        "revenue_annual_yoy_growth_ttm",
        "net_margin",
        "gross_margin",
        "debt_to_equity",
        "current_ratio",
        f"Recommend.All|{tf}",
        f"Recommend.MA|{tf}",
        f"Recommend.Other|{tf}",
        f"RSI|{tf}",
        f"MACD.macd|{tf}",
        f"MACD.signal|{tf}",
        f"EMA20|{tf}",
        f"EMA50|{tf}",
        f"EMA200|{tf}",
        f"Stoch.K|{tf}",
        f"Stoch.D|{tf}",
        f"BB.upper|{tf}",
        f"BB.lower|{tf}",
        "price_52_week_high",
        "price_52_week_low",
    ]

    # ── ATTEMPT 1: Full Filter Ketat ─────────────────────────
    try:
        print(f"   [1/3] Full filter [{tf}]...")
        count, df = (
            Query()
            .set_markets("malaysia")
            .select(*COLUMNS)
            .where(
                col("market_cap_basic")               > 0,
                col(f"volume|{tf}")                   > 2_000_000,
                col("close")                          >= 0.15,
                col("close")                          <= 6.00,
                col(f"RSI|{tf}")                      >= 55,
                col(f"RSI|{tf}")                      <= 75,
                col(f"Recommend.All|{tf}")            >= 0.1,
                col(f"Recommend.MA|{tf}")             >= 0.1,
                col(f"Recommend.Other|{tf}")          >= 0.1,
                col(f"EMA20|{tf}")                    > col(f"EMA50|{tf}"),
                col(f"EMA50|{tf}")                    > col(f"EMA200|{tf}"),
                col("close")                          > col(f"EMA20|{tf}"),
                col(f"MACD.macd|{tf}")                > col(f"MACD.signal|{tf}"),
                col(f"change|{tf}")                   > 0,
                col("earnings_per_share_diluted_ttm") > 0,
                col("return_on_equity")               > 10,
                col("net_margin")                     > 5,
                col("debt_to_equity")                 < 1.0,
                col("revenue_annual_yoy_growth_ttm")  > 0,
                col("price_earnings_ttm")             > 0,
                col("price_earnings_ttm")             < 30,
            )
            .order_by(f"volume|{tf}", ascending=False)
            .limit(500)
            .get_scanner_data()
        )
        if count > 0:
            print(f"   ✅ Full filter: {count} stocks")
            return df
        # ✅ FIX — print MESTI selepas if block, bukan dalam if
        print(f"   ⚠️  0 stocks → try relaxed...")
    except Exception as e:
        print(f"   ⚠️  Full filter error: {e}")

    # ── ATTEMPT 2: Relaxed Filter ────────────────────────────
    try:
        print(f"   [2/3] Relaxed filter [{tf}]...")
        count, df = (
            Query()
            .set_markets("malaysia")
            .select(*COLUMNS)
            .where(
                col("market_cap_basic")               > 0,
                col(f"volume|{tf}")                   > 2_000_000,
                col("close")                          >= 0.15,
                col("close")                          <= 6.00,
                col(f"RSI|{tf}")                      >= 55,
                col(f"RSI|{tf}")                      <= 75,
                col(f"Recommend.All|{tf}")            >= 0.1,
                col(f"Recommend.MA|{tf}")             >= 0.1,
                col(f"EMA20|{tf}")                    > col(f"EMA50|{tf}"),
                col(f"EMA50|{tf}")                    > col(f"EMA200|{tf}"),
                col("close")                          > col(f"EMA20|{tf}"),
                col(f"MACD.macd|{tf}")                > col(f"MACD.signal|{tf}"),
                col("earnings_per_share_diluted_ttm") > 0,
                col("return_on_equity")               > 5,
                col("net_margin")                     > 3,
                col("debt_to_equity")                 < 1.5,
            )
            .order_by(f"volume|{tf}", ascending=False)
            .limit(300)
            .get_scanner_data()
        )
        if count > 0:
            print(f"   ✅ Relaxed filter: {count} stocks")
            return df
        print(f"   ⚠️  0 stocks → try minimal...")
    except Exception as e:
        print(f"   ⚠️  Relaxed filter error: {e}")

    # ── ATTEMPT 3: Minimal Filter ────────────────────────────
    try:
        print(f"   [3/3] Minimal filter [{tf}]...")
        count, df = (
            Query()
            .set_markets("malaysia")
            .select(*COLUMNS)
            .where(
                col("market_cap_basic")    > 0,
                col(f"volume|{tf}")        > 2_000_000,
                col("close")               >= 0.15,
                col("close")               <= 6.00,
                col(f"RSI|{tf}")           >= 55,
                col(f"RSI|{tf}")           <= 75,
                col(f"Recommend.All|{tf}") >= 0.1,
                col(f"EMA20|{tf}")         > col(f"EMA50|{tf}"),
                col("close")               > col(f"EMA20|{tf}"),
            )
            .order_by(f"volume|{tf}", ascending=False)
            .limit(200)
            .get_scanner_data()
        )
        print(f"   ✅ Minimal filter: {count} stocks")
        return df
    except Exception as e:
        print(f"   ❌ All filters failed: {e}")
        return pd.DataFrame()

# ════════════════════════════════════════════════════════════
# PROCESS FUNCTION
# ════════════════════════════════════════════════════════════
def process_data(df, tf):
    if df is None or len(df) == 0:
        return []

    rename = {
        "name"                           : "Symbol",
        "description"                    : "Company",
        "sector"                         : "Sector",
        "market_cap_basic"               : "Market_Cap",
        "close"                          : "Price",
        f"change|{tf}"                   : "Chg_Pct",
        f"volume|{tf}"                   : "Volume",
        "average_volume_10d_calc"        : "Avg_Vol",
        "earnings_per_share_diluted_ttm" : "EPS",
        "price_earnings_ttm"             : "PE",
        "price_to_book_fwd"              : "PB",
        "dividends_yield_current"        : "Div_Yield",
        "return_on_equity"               : "ROE",
        "return_on_assets"               : "ROA",
        "revenue_annual_yoy_growth_ttm"  : "Rev_Growth",
        "net_margin"                     : "Net_Margin",
        "gross_margin"                   : "Gross_Margin",
        "debt_to_equity"                 : "DE_Ratio",
        "current_ratio"                  : "CR",
        f"Recommend.All|{tf}"            : "Tech_Raw",
        f"Recommend.MA|{tf}"             : "MA_Raw",
        f"Recommend.Other|{tf}"          : "Osc_Raw",
        f"RSI|{tf}"                      : "RSI",
        f"MACD.macd|{tf}"                : "MACD",
        f"MACD.signal|{tf}"              : "MACD_Sig",
        f"EMA20|{tf}"                    : "EMA20",
        f"EMA50|{tf}"                    : "EMA50",
        f"EMA200|{tf}"                   : "EMA200",
        f"Stoch.K|{tf}"                  : "Stoch_K",
        f"Stoch.D|{tf}"                  : "Stoch_D",
        f"BB.upper|{tf}"                 : "BB_Up",
        f"BB.lower|{tf}"                 : "BB_Lo",
        "price_52_week_high"             : "High_52W",
        "price_52_week_low"              : "Low_52W",
    }

    rename = {k: v for k, v in rename.items() if k in df.columns}
    df = df.rename(columns=rename)

    if "ticker" in df.columns:
        df = df.drop(columns=["ticker"])

    df["Tech_Signal"] = df["Tech_Raw"].apply(rating_label) \
        if "Tech_Raw" in df.columns else "N/A"
    df["RSI_Zone"]    = df["RSI"].apply(rsi_zone) \
        if "RSI" in df.columns else "N/A"
    df["EMA_Trend"]   = df.apply(
        lambda r: ema_trend(r.get("EMA20"), r.get("EMA50"), r.get("EMA200")),
        axis=1)
    df["MACD_Label"]  = df.apply(
        lambda r: macd_label(r.get("MACD"), r.get("MACD_Sig")),
        axis=1)

    print("      Running Elliott Wave analysis...")
    ew_results      = df.apply(elliott_wave_analysis, axis=1)
    df["EW_Wave"]   = ew_results.apply(lambda x: x.get("wave",      "N/A"))
    df["EW_Desc"]   = ew_results.apply(lambda x: x.get("wave_desc", ""))
    df["Buy_Price"] = ew_results.apply(lambda x: x.get("buy_price",  0))
    df["Sell_Price"]= ew_results.apply(lambda x: x.get("sell_price", 0))
    df["Stop_Loss"] = ew_results.apply(lambda x: x.get("stop_loss",  0))
    df["Direction"] = ew_results.apply(lambda x: x.get("direction",  "N/A"))
    df["Confidence"]= ew_results.apply(lambda x: x.get("confidence", 0))
    df["RR_Ratio"]  = ew_results.apply(lambda x: x.get("rr_ratio",   0))
    df["Fib_382"]   = ew_results.apply(lambda x: x.get("fib_382",    0))
    df["Fib_618"]   = ew_results.apply(lambda x: x.get("fib_618",    0))
    print("      Running Trader Pro & Robot Algo signals...")
    df["Trader_Pro"] = df.apply(trader_pro_signal, axis=1)
    df["Robot_Algo"] = df.apply(robot_algo_signal, axis=1)
    df["Score"] = df.apply(score_stock, axis=1)
    df["Score"] = df.apply(score_stock, axis=1)
    df["Grade"] = df["Score"].apply(score_grade)

    before = len(df)

    # ✅ FIX — indentasi mesti DALAM fungsi (8 spaces)
    if "Price" in df.columns:
        df = df[df["Price"].apply(safe_float) >= 0.15]
        df = df[df["Price"].apply(safe_float) <= 6.00]

    df = df[~df["Grade"].isin(["D", "C"])]
    df = df[~df["RSI_Zone"].isin(["Extreme OB"])]
    df = df[df["EMA_Trend"].isin(["Perfect Bull", "Partial Bull"])]
    df = df[df["Score"] >= 50]
    df = df[df["MACD_Label"].isin(["Bull+Zero", "Bull-Zero"])]
    df = df[df["Tech_Signal"].isin(["Strong Buy", "Buy"])]
    after = len(df)
    print(f"      Post-filter: {before} → {after} stocks")

    df = df.sort_values("Score", ascending=False)
    df = df.round(2)
    df = df.where(pd.notnull(df), "")
    return df.to_dict("records")


# ════════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return get_dashboard_html()

@app.route("/health")
def health():
    return jsonify({
        "status"  : "ok",
        "time"    : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message" : "Flask server is running!"
    })

# ✅ FIX — tf_map lengkap semua timeframe
@app.route("/api/screener/<tf>")
def screener(tf):
    try:
        tf_map = {
            "monthly" : "1M",   # ← TAMBAH
            "weekly"  : "1W",
            "daily"   : "1D",
            "4h"      : "240",
            "1h"      : "60",   # ← TAMBAH
            "15m"     : "15",   # ← TAMBAH
            "5m"      : "5",
                    }
        tf_code = tf_map.get(tf.lower(), "1D")
        print(f"Fetching [{tf}] → [{tf_code}]...")

        df   = fetch_screener(tf_code)
        data = process_data(df, tf_code)

        print(f"  → {len(data)} stocks returned")

        up_count = sum(
            1 for r in data
            if r.get("Direction", "") and "UP" in r.get("Direction", "")
        )
        total  = len(data) if len(data) > 0 else 1
        up_pct = round(up_count / total * 100, 1)

        if up_pct >= 70:   mkt = "🟢 BULLISH MARKET"
        elif up_pct >= 55: mkt = "🟡 MILD BULLISH"
        elif up_pct >= 45: mkt = "⚪ NEUTRAL/SIDEWAYS"
        elif up_pct >= 30: mkt = "🟠 MILD BEARISH"
        else:              mkt = "🔴 BEARISH MARKET"

        return jsonify({
            "status"           : "ok",
            "timeframe"        : tf,
            "count"            : len(data),
            "updated"          : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market_direction" : mkt,
            "market_pct"       : up_pct,
            "data"             : data
        })

    except Exception as e:
        print(f"ERROR [{tf}]: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ✅ FIX — best_stocks: key konsisten + indentasi betul + koma dalam sum()
@app.route("/api/best")
def best_stocks():
    try:
        all_syms = {}
        all_data = {}

        for name, tf_code in TIMEFRAMES.items():
            print(f"Fetching best [{name}]...")
            df   = fetch_screener(tf_code)
            data = process_data(df, tf_code)
            syms = {d["Symbol"] for d in data if d.get("Symbol")}
            all_syms[name] = syms
            all_data[name] = {d["Symbol"]: d for d in data}
            print(f"  → {len(data)} stocks")

        # ✅ FIX — key mesti SAMA dengan TIMEFRAMES dict
        mn  = all_syms.get("Monthly_1M",      set())
        wk  = all_syms.get("Weekly_1W",       set())
        dy  = all_syms.get("Daily_1D",        set())
        h4  = all_syms.get("4Hour_4H",        set())
        h1  = all_syms.get("1Hour_1H",        set())
        m15 = all_syms.get("15Minutes_15min", set())
        m5  = all_syms.get("5Minutes_5min",   set())

        best = []
        # ✅ FIX — union semua set
        for sym in (mn | wk | dy | h4 | h1 | m15 | m5):
            d = (
                all_data.get("Monthly_1M",      {}).get(sym) or
                all_data.get("Weekly_1W",        {}).get(sym) or
                all_data.get("Daily_1D",         {}).get(sym) or
                all_data.get("4Hour_4H",         {}).get(sym) or
                all_data.get("1Hour_1H",         {}).get(sym) or
                all_data.get("15Minutes_15min",  {}).get(sym) or
                all_data.get("5Minutes_5min",    {}).get(sym) or {}
            )
            if d:
                d = dict(d)
                d["In_Monthly"] = sym in mn
                d["In_Weekly"]  = sym in wk
                d["In_Daily"]   = sym in dy
                d["In_4H"]      = sym in h4
                d["In_1H"]      = sym in h1
                d["In_15Min"]   = sym in m15
                d["In_5Min"]    = sym in m5
                # ✅ FIX — koma betul dalam sum([...])
                d["TF_Count"]   = sum([
                    sym in mn,
                    sym in wk,
                    sym in dy,
                    sym in h4,
                    sym in h1,
                    sym in m15,
                    sym in m5,
                ])
                best.append(d)

        best.sort(key=lambda x: (
            -x.get("TF_Count", 0),
            -float(x.get("Score", 0) or 0)
        ))

        print(f"Best stocks total: {len(best)}")

        return jsonify({
            "status"  : "ok",
            "count"   : len(best),
            "updated" : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data"    : best
        })

    except Exception as e:
        print(f"ERROR best: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500
# ════════════════════════════════════════════════════════════
# UNIVERSAL STOCK SEARCH — Tambah selepas best_stocks()
# ════════════════════════════════════════════════════════════
@app.route("/api/search/<symbol>")
def search_stock(symbol):
    try:
        sym_upper = symbol.strip().upper()
        print(f"[SEARCH] Mencari: {sym_upper}")

        COLUMNS = [
            "name", "description", "sector",
            "market_cap_basic", "close",
            "change|1D", "volume|1D",
            "average_volume_10d_calc",
            "earnings_per_share_diluted_ttm",
            "price_earnings_ttm",
            "price_to_book_fwd",
            "dividends_yield_current",
            "return_on_equity",
            "return_on_assets",
            "revenue_annual_yoy_growth_ttm",
            "net_margin",
            "gross_margin",
            "debt_to_equity",
            "current_ratio",
            "Recommend.All|1D",
            "Recommend.MA|1D",
            "Recommend.Other|1D",
            "RSI|1D",
            "MACD.macd|1D",
            "MACD.signal|1D",
            "EMA20|1D",
            "EMA50|1D",
            "EMA200|1D",
            "Stoch.K|1D",
            "Stoch.D|1D",
            "BB.upper|1D",
            "BB.lower|1D",
            "price_52_week_high",
            "price_52_week_low",
        ]

        results = []

        # ── ATTEMPT 1: Exact match by symbol ─────────────────
        try:
            print(f"   [1/3] Exact match: {sym_upper}")
            count, df = (
                Query()
                .set_markets("malaysia")
                .select(*COLUMNS)
                .where(col("name") == sym_upper)
                .limit(5)
                .get_scanner_data()
            )
            if count > 0:
                print(f"   ✅ Exact: {count} result")
                results = process_search_results(df)
        except Exception as e:
            print(f"   ⚠️  Exact error: {e}")

        # ── ATTEMPT 2: Description contains keyword ───────────
        if not results:
            try:
                print(f"   [2/3] Description search: {sym_upper}")
                count, df = (
                    Query()
                    .set_markets("malaysia")
                    .select(*COLUMNS)
                    .where(
                        col("description").like(f"%{sym_upper}%")
                    )
                    .order_by("market_cap_basic", ascending=False)
                    .limit(20)
                    .get_scanner_data()
                )
                if count > 0:
                    print(f"   ✅ Description: {count} results")
                    results = process_search_results(df)
            except Exception as e:
                print(f"   ⚠️  Description error: {e}")

        # ── ATTEMPT 3: Name contains keyword ──────────────────
        if not results:
            try:
                print(f"   [3/3] Name broad search: {sym_upper}")
                count, df = (
                    Query()
                    .set_markets("malaysia")
                    .select(*COLUMNS)
                    .where(
                        col("name").like(f"%{sym_upper}%")
                    )
                    .order_by("market_cap_basic", ascending=False)
                    .limit(20)
                    .get_scanner_data()
                )
                if count > 0:
                    print(f"   ✅ Name broad: {count} results")
                    results = process_search_results(df)
            except Exception as e:
                print(f"   ⚠️  Name broad error: {e}")

        print(f"   → Search selesai: {len(results)} kaunter")

        return jsonify({
            "status"  : "ok",
            "query"   : sym_upper,
            "count"   : len(results),
            "updated" : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data"    : results
        })

    except Exception as e:
        print(f"ERROR search [{symbol}]: {e}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ════════════════════════════════════════════════════════════
# PROCESS SEARCH RESULTS — Tanpa quality filter
# ════════════════════════════════════════════════════════════
def process_search_results(df):
    """
    Sama seperti process_data() TETAPI:
    1. Guna tf = "1D" sahaja (fixed)
    2. TIADA quality filter — papar semua kaunter
    3. Tambah Is_Search = True flag
    """
    if df is None or len(df) == 0:
        return []

    tf = "1D"

    rename = {
        "name"                           : "Symbol",
        "description"                    : "Company",
        "sector"                         : "Sector",
        "market_cap_basic"               : "Market_Cap",
        "close"                          : "Price",
        f"change|{tf}"                   : "Chg_Pct",
        f"volume|{tf}"                   : "Volume",
        "average_volume_10d_calc"        : "Avg_Vol",
        "earnings_per_share_diluted_ttm" : "EPS",
        "price_earnings_ttm"             : "PE",
        "price_to_book_fwd"              : "PB",
        "dividends_yield_current"        : "Div_Yield",
        "return_on_equity"               : "ROE",
        "return_on_assets"               : "ROA",
        "revenue_annual_yoy_growth_ttm"  : "Rev_Growth",
        "net_margin"                     : "Net_Margin",
        "gross_margin"                   : "Gross_Margin",
        "debt_to_equity"                 : "DE_Ratio",
        "current_ratio"                  : "CR",
        f"Recommend.All|{tf}"            : "Tech_Raw",
        f"Recommend.MA|{tf}"             : "MA_Raw",
        f"Recommend.Other|{tf}"          : "Osc_Raw",
        f"RSI|{tf}"                      : "RSI",
        f"MACD.macd|{tf}"                : "MACD",
        f"MACD.signal|{tf}"              : "MACD_Sig",
        f"EMA20|{tf}"                    : "EMA20",
        f"EMA50|{tf}"                    : "EMA50",
        f"EMA200|{tf}"                   : "EMA200",
        f"Stoch.K|{tf}"                  : "Stoch_K",
        f"Stoch.D|{tf}"                  : "Stoch_D",
        f"BB.upper|{tf}"                 : "BB_Up",
        f"BB.lower|{tf}"                 : "BB_Lo",
        "price_52_week_high"             : "High_52W",
        "price_52_week_low"              : "Low_52W",
    }

    rename = {k: v for k, v in rename.items() if k in df.columns}
    df = df.rename(columns=rename)

    if "ticker" in df.columns:
        df = df.drop(columns=["ticker"])

    # ── Derived columns ───────────────────────────────────────
    df["Tech_Signal"] = df["Tech_Raw"].apply(rating_label) \
        if "Tech_Raw" in df.columns else "N/A"
    df["RSI_Zone"]    = df["RSI"].apply(rsi_zone) \
        if "RSI" in df.columns else "N/A"
    df["EMA_Trend"]   = df.apply(
        lambda r: ema_trend(r.get("EMA20"), r.get("EMA50"), r.get("EMA200")),
        axis=1)
    df["MACD_Label"]  = df.apply(
        lambda r: macd_label(r.get("MACD"), r.get("MACD_Sig")),
        axis=1)

    # ── Elliott Wave ──────────────────────────────────────────
    ew_results       = df.apply(elliott_wave_analysis, axis=1)
    df["EW_Wave"]    = ew_results.apply(lambda x: x.get("wave",      "N/A"))
    df["EW_Desc"]    = ew_results.apply(lambda x: x.get("wave_desc", ""))
    df["Buy_Price"]  = ew_results.apply(lambda x: x.get("buy_price",  0))
    df["Sell_Price"] = ew_results.apply(lambda x: x.get("sell_price", 0))
    df["Stop_Loss"]  = ew_results.apply(lambda x: x.get("stop_loss",  0))
    df["Direction"]  = ew_results.apply(lambda x: x.get("direction",  "N/A"))
    df["Confidence"] = ew_results.apply(lambda x: x.get("confidence", 0))
    df["RR_Ratio"]   = ew_results.apply(lambda x: x.get("rr_ratio",   0))
    df["Fib_382"]    = ew_results.apply(lambda x: x.get("fib_382",    0))
    df["Fib_618"]    = ew_results.apply(lambda x: x.get("fib_618",    0))

    # ── Score & Grade ─────────────────────────────────────────
    df["Score"]      = df.apply(score_stock, axis=1)
    df["Grade"]      = df["Score"].apply(score_grade)

    # ── Signals ───────────────────────────────────────────────
    df["Trader_Pro"] = df.apply(trader_pro_signal, axis=1)
    df["Robot_Algo"] = df.apply(robot_algo_signal, axis=1)

    # ── Tag search result ─────────────────────────────────────
    df["Is_Search"]  = True

    # ── TIADA quality filter di sini ──────────────────────────
    df = df.round(2)
    df = df.where(pd.notnull(df), "")
    return df.to_dict("records")

# ════════════════════════════════════════════════════════════
# HTML DASHBOARD
# ════════════════════════════════════════════════════════════
def get_dashboard_html():
    return """<!DOCTYPE html>
<html lang="ms">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🏆 Bullish Screener — Malaysia</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Arial,sans-serif;background:#0d1117;color:#e6edf3}
.header{background:linear-gradient(135deg,#1f3864,#2d5a9e);padding:20px 30px;
  display:flex;justify-content:space-between;align-items:center;
  position:sticky;top:0;z-index:100;box-shadow:0 4px 20px rgba(0,0,0,.5)}
.header h1{font-size:22px;font-weight:700}
.header h1 span{color:#ffd700}
.last-updated{font-size:12px;color:#8b949e;text-align:right}
.stats-bar{display:flex;gap:15px;padding:15px 30px;background:#161b22;
  border-bottom:1px solid #30363d;flex-wrap:wrap}
.stat-card{background:#21262d;border:1px solid #30363d;border-radius:8px;
  padding:10px 18px;text-align:center;min-width:100px}
.stat-card .num{font-size:24px;font-weight:700;color:#58a6ff}
.stat-card .lbl{font-size:11px;color:#8b949e;margin-top:2px}
.tabs{display:flex;gap:5px;padding:15px 30px 0;background:#161b22;
  border-bottom:1px solid #30363d;flex-wrap:wrap}
.tab-btn{padding:10px 20px;border:1px solid #30363d;border-bottom:none;
  border-radius:8px 8px 0 0;cursor:pointer;font-size:13px;font-weight:600;
  background:#21262d;color:#8b949e;transition:all .2s}
.tab-btn:hover{background:#2d333b;color:#e6edf3}
.tab-btn.active{background:#1f3864;color:#fff;border-color:#58a6ff}
.tab-btn.gold.active{background:#7d6608;border-color:#ffd700;color:#ffd700}
.controls{display:flex;gap:10px;padding:15px 30px;background:#161b22;
  align-items:center;flex-wrap:wrap}
.search-box{padding:8px 14px;background:#21262d;border:1px solid #30363d;
  border-radius:6px;color:#e6edf3;font-size:13px;width:220px}
.search-box:focus{outline:none;border-color:#58a6ff}
.refresh-btn{padding:8px 18px;background:#238636;border:none;border-radius:6px;
  color:#fff;cursor:pointer;font-size:13px;font-weight:600}
.refresh-btn:hover{background:#2ea043}
.refresh-btn:disabled{background:#21262d;color:#8b949e;cursor:not-allowed}
.filter-select{padding:8px 12px;background:#21262d;border:1px solid #30363d;
  border-radius:6px;color:#e6edf3;font-size:13px}
.count-badge{background:#1f3864;color:#58a6ff;padding:4px 12px;
  border-radius:20px;font-size:12px;font-weight:600}
.filter-info{font-size:11px;color:#8b949e;padding:5px 10px;background:#161b22;
  border-radius:4px;border:1px solid #30363d}
.table-container{padding:0 30px 30px;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12px;margin-top:15px}
thead th{background:#1f3864;color:#fff;padding:10px 12px;text-align:center;
  font-weight:600;font-size:11px;cursor:pointer;white-space:nowrap;
  border:1px solid #30363d;user-select:none;position:sticky;top:0}
thead th:hover{background:#2d5a9e}
thead th.sort-asc::after{content:" ↑";color:#ffd700}
thead th.sort-desc::after{content:" ↓";color:#ffd700}
tbody tr{border-bottom:1px solid #21262d;transition:background .15s}
tbody tr:hover{background:#1c2128!important}
tbody tr:nth-child(even){background:#161b22}
tbody tr:nth-child(odd){background:#0d1117}
td{padding:8px 12px;text-align:center;border:1px solid #21262d;white-space:nowrap}
td.left{text-align:left}
td.symbol{font-weight:700;color:#58a6ff;cursor:pointer}
td.symbol:hover{color:#79c0ff;text-decoration:underline}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;
  font-size:10px;font-weight:700}
.b-sb{background:#1a4731;color:#56d364}
.b-b{background:#0d2d1a;color:#3fb950}
.b-n{background:#3d2f00;color:#d29922}
.b-s{background:#3d1a1a;color:#f85149}
.b-ss{background:#5a0000;color:#ff7b72}
.b-sw{background:#1a4731;color:#56d364}
.b-bu{background:#0d2d1a;color:#3fb950}
.b-ob{background:#3d2f00;color:#d29922}
.b-os{background:#2d1b69;color:#d2a8ff}
.b-pb{background:#1a4731;color:#56d364}
.b-pa{background:#0d2d1a;color:#3fb950}
.b-mx{background:#3d2f00;color:#d29922}
.b-br{background:#5a0000;color:#ff7b72}
.b-bz{background:#1a4731;color:#56d364}
.b-bm{background:#0d2d1a;color:#3fb950}
.b-rz{background:#3d2f00;color:#d29922}
.b-rm{background:#5a0000;color:#ff7b72}
.g-ap{background:#7d6608;color:#ffd700;font-size:13px}
.g-a{background:#1a4731;color:#56d364}
.g-bp{background:#0d2d1a;color:#3fb950}
.g-b{background:#3d2f00;color:#d29922}
.g-c{background:#3d1a1a;color:#f85149}
.g-d{background:#5a0000;color:#ff7b72}
.chg-p{color:#56d364;font-weight:600}
.chg-n{color:#f85149;font-weight:600}
.tf-y{color:#56d364;font-weight:700}
.tf-n{color:#30363d}
.loading{text-align:center;padding:60px;color:#8b949e}
.spinner{width:40px;height:40px;border:3px solid #30363d;
  border-top-color:#58a6ff;border-radius:50%;
  animation:spin .8s linear infinite;margin:0 auto 15px}
@keyframes spin{to{transform:rotate(360deg)}}
.score-bar{display:flex;align-items:center;gap:6px}
.score-fill{height:6px;border-radius:3px;min-width:4px}
.score-num{font-weight:700;font-size:12px}
.empty{text-align:center;padding:60px;color:#8b949e}
.ew-wave{font-weight:700;font-size:11px}
.ew-w1{color:#58a6ff}
.ew-w3{color:#56d364;font-size:12px}
.ew-w5{color:#d29922}
.ew-w2{color:#d2a8ff}
.ew-w4{color:#ffa657}
.ew-abc{color:#f85149}
.dir-sup{background:#0d2d1a;color:#56d364;padding:3px 8px;
  border-radius:4px;font-weight:700;font-size:11px}
.dir-up{background:#1a4731;color:#3fb950;padding:3px 8px;
  border-radius:4px;font-weight:700;font-size:11px}
.dir-sd{background:#3d2f00;color:#d29922;padding:3px 8px;
  border-radius:4px;font-weight:700;font-size:11px}
.dir-dn{background:#5a0000;color:#ff7b72;padding:3px 8px;
  border-radius:4px;font-weight:700;font-size:11px}
.dir-pb{background:#2d1b69;color:#d2a8ff;padding:3px 8px;
  border-radius:4px;font-weight:700;font-size:11px}
.price-buy{color:#56d364;font-weight:700}
.price-sell{color:#f85149;font-weight:700}
.price-sl{color:#d29922;font-weight:600}
.rr-good{color:#56d364;font-weight:700}
.rr-ok{color:#d29922;font-weight:600}
.rr-bad{color:#f85149}
.conf-high{color:#56d364;font-weight:700}
.conf-mid{color:#d29922}
.conf-low{color:#f85149}
.mkt-banner{padding:10px 30px;text-align:center;font-weight:700;
  font-size:14px;border-bottom:2px solid #30363d;display:none}
/* ── 6 KOLUM UTAMA — KEY INDICATOR — Font hijau sahaja ── */
.th-key{
  color:#00ff88 !important;
  font-weight:800 !important
}
.th-key:hover{
  background:#2d5a9e !important
}
.td-key{}

/* ── TRADER PRO ─────────────────────────────────────── */
.tp-sb{background:#003d20;color:#00ff88;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px;
  border:1px solid #00ff88}
.tp-bl{background:#0d2d1a;color:#56d364;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.tp-al{background:#3d3000;color:#ffd700;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.tp-wp{background:#2d1f00;color:#ffa657;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.tp-mn{background:#0d1b2e;color:#79c0ff;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.tp-wl{background:#21262d;color:#8b949e;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.tp-sk{background:#161b22;color:#484f58;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.tp-ab{background:#5a0000;color:#ff4444;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px;
  animation:blink 1s infinite}
.tp-ov{background:#2d1b69;color:#d2a8ff;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}

/* ── ROBOT ALGO ──────────────────────────────────────── */
.ra-ex{background:#003d20;color:#00ff88;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px;
  border:1px solid #00ff88;
  animation:pulse 1.5s infinite}
.ra-qu{background:#0d2d1a;color:#56d364;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.ra-ar{background:#1a3a00;color:#7ee787;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.ra-tr{background:#3d2f00;color:#d29922;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.ra-li{background:#21262d;color:#8b949e;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.ra-nv{background:#5a0000;color:#ff7b72;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.ra-pa{background:#161b22;color:#484f58;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}
.ra-iv{background:#3d1a1a;color:#f85149;padding:3px 7px;
  border-radius:4px;font-weight:700;font-size:10px}

@keyframes pulse{
  0%,100%{box-shadow:0 0 0 0 rgba(0,255,136,0.5)}
  50%{box-shadow:0 0 0 8px rgba(0,255,136,0)}
}
@keyframes blink{
  0%,100%{opacity:1}50%{opacity:0.3}
}

/* ── SEARCH MODE INDICATOR ───────────────────────────────── */
.search-mode-badge{
  display:none;
  padding:4px 12px;
  background:#2d1b69;
  color:#d2a8ff;
  border:1px solid #6e40c9;
  border-radius:20px;
  font-size:11px;
  font-weight:700;
  animation:pulse 1.5s infinite
}
.search-mode-badge.active{ display:inline-block }

.search-box-wrap{
  position:relative;
  display:flex;
  align-items:center
}
.search-box-wrap .clear-btn{
  position:absolute;
  right:8px;
  background:none;
  border:none;
  color:#8b949e;
  cursor:pointer;
  font-size:14px;
  padding:0;
  display:none
}
.search-box-wrap .clear-btn.show{ display:block }
.search-box-wrap .search-spinner{
  position:absolute;
  right:28px;
  width:14px;
  height:14px;
  border:2px solid #30363d;
  border-top-color:#58a6ff;
  border-radius:50%;
  animation:spin .6s linear infinite;
  display:none
}
.search-box-wrap .search-spinner.show{ display:block }

/* ── SEARCH RESULT TABLE — highlight berbeza ─────────────── */
.search-result-row{
  background:#1a1a2e !important;
  border-left:3px solid #6e40c9 !important
}
.search-result-row:hover{
  background:#1f1f3a !important
}
.search-info-bar{
  padding:8px 30px;
  background:#1a1a2e;
  border-bottom:1px solid #6e40c9;
  font-size:12px;
  color:#d2a8ff;
  display:none
}
.search-info-bar.show{ display:block }
.is-search-badge{
  background:#2d1b69;
  color:#d2a8ff;
  padding:2px 6px;
  border-radius:3px;
  font-size:9px;
  font-weight:700;
  margin-left:4px
}

</style>
</head>
<body>
<div class="header">
  <h1>🏆 <span>Bullish Screener</span> — Malaysia Market</h1>
  <div class="last-updated" id="lastUpdated">Klik Refresh untuk muat data</div>
</div>
<div id="mktBanner" class="mkt-banner"></div>

<div class="stats-bar">
  <div class="stat-card">
    <div class="num" id="sTotal">—</div>
    <div class="lbl">Total Stocks</div>
  </div>
  <div class="stat-card">
    <div class="num" id="sGradeA">—</div>
    <div class="lbl">Grade A+/A</div>
  </div>
  <div class="stat-card">
    <div class="num" id="sBest">—</div>
    <div class="lbl">Best (All TF)</div>
  </div>
  <div class="stat-card">
    <div class="num" id="sAvg">—</div>
    <div class="lbl">Avg Score</div>
  </div>
  <div class="stat-card">
    <div class="num" id="sPositive">—</div>
    <div class="lbl">Chg% Positif</div>
  </div>
  <div class="stat-card" id="mktCard" style="min-width:180px">
    <div class="num" id="sMktDir" style="font-size:13px">—</div>
    <div class="lbl">Market Direction</div>
  </div>
  <div class="stat-card">
    <div class="num" id="sMktPct" style="color:#56d364">—</div>
    <div class="lbl">Bullish %</div>
  </div>
</div>

<!-- ✅ TABS — Monthly ditambah, 5m ID diperbetul -->
<div class="tabs">
  <button class="tab-btn" onclick="switchTab('monthly')" id="tab-monthly">📆 Monthly</button>
  <button class="tab-btn" onclick="switchTab('weekly')"  id="tab-weekly">📅 Weekly</button>
  <button class="tab-btn active" onclick="switchTab('daily')" id="tab-daily">📊 Daily</button>
  <button class="tab-btn" onclick="switchTab('4h')"      id="tab-4h">⏱️ 4 Hour</button>
  <button class="tab-btn" onclick="switchTab('1h')"      id="tab-1h">🕐 1 Hour</button>
  <button class="tab-btn" onclick="switchTab('15m')"     id="tab-15m">⏲️ 15 Min</button>
  <button class="tab-btn" onclick="switchTab('5m')"      id="tab-5m">⚡ 5 Min</button>
  <button class="tab-btn gold" onclick="switchTab('best')" id="tab-best">⭐ Best Stocks</button>
</div>

<div id="searchInfoBar" class="search-info-bar">
  🔍 <strong>Mode Carian Universal</strong> — Menunjukkan hasil carian
  "<span id="searchQueryLabel"></span>" terus dari TradingView.
  Data ini <strong>tidak ditapis</strong> oleh kriteria bullish screener.
  <button onclick="clearSearch()"
    style="margin-left:15px;padding:2px 10px;background:#6e40c9;
           border:none;border-radius:4px;color:#fff;cursor:pointer;
           font-size:11px">
    ✕ Kembali ke Screener
  </button>
</div>

<div class="controls">
  <div class="search-box-wrap">
    <input type="text" class="search-box" id="searchBox"
           placeholder="🔍 Cari symbol / syarikat... (contoh: TENAGA)"
           oninput="onSearchInput(this.value)"
           onkeydown="onSearchKeydown(event)"
           autocomplete="off"
           style="width:260px;padding-right:50px">
    <div class="search-spinner" id="searchSpinner"></div>
    <button class="clear-btn" id="clearBtn" onclick="clearSearch()">✕</button>
  </div>

  <select class="filter-select" id="gradeFilter" onchange="filterTable()">
    <option value="">Semua Grade</option>
    <option value="A+">A+ 🏆</option>
    <option value="A">A ⭐</option>
    <option value="B+">B+ ✅</option>
    <option value="B">B 👍</option>
  </select>

  <select class="filter-select" id="sectorFilter" onchange="filterTable()">
    <option value="">Semua Sektor</option>
  </select>

  <select class="filter-select" id="emaFilter" onchange="filterTable()">
    <option value="">Semua EMA</option>
    <option value="Perfect Bull">Perfect Bull ⭐</option>
    <option value="Partial Bull">Partial Bull ✅</option>
  </select>

  <button class="refresh-btn" id="refreshBtn" onclick="loadData()">
    🔄 Refresh Data
  </button>

  <span class="count-badge" id="countBadge">0 stocks</span>
  <span class="search-mode-badge" id="searchModeBadge">
    🔍 SEARCH MODE
  </span>
  <span class="filter-info">
    ✅ Filter: Bullish + Profit | 💰 RM0.15~RM6.00 | RSI 55~75
  </span>
</div>
<div class="table-container">
  <div class="loading" id="loadingDiv">
    <div class="spinner"></div>
    <div>Klik Refresh untuk muat data dari TradingView...</div>
  </div>
  <div id="tableDiv" style="display:none">
    <table id="mainTable">
      <thead id="tableHead"></thead>
      <tbody id="tableBody"></tbody>
    </table>
  </div>
  <div class="empty" id="emptyDiv" style="display:none">
    <div style="font-size:48px">📭</div>
    <div style="margin-top:15px">Tiada saham yang memenuhi kriteria bullish.</div>
    <div style="margin-top:8px;font-size:12px;color:#58a6ff">
      Semua saham yang tidak berkualiti telah ditapis keluar.
    </div>
  </div>
</div>

<script>
let currentTab="daily", allData={}, sortCol="Score", sortDir=-1;

// ── TOTAL TF COUNT — update ikut bilangan TF sebenar ─────
const TOTAL_TF = 7;  // Monthly,Weekly,Daily,4H,1H,15M,5M

// ── ELLIOTT WAVE BADGES ───────────────────────────────────
function ewBadge(v){
  if(!v||v==="N/A") return "—";
  const m={"Wave 1":"ew-w1","Wave 3":"ew-w3","Wave 5":"ew-w5",
            "Wave 2":"ew-w2","Wave 4":"ew-w4","Wave A/B/C":"ew-abc"};
  const icons={"Wave 1":"①","Wave 3":"③","Wave 5":"⑤",
                "Wave 2":"②","Wave 4":"④","Wave A/B/C":"ABC"};
  return `<span class="ew-wave ${m[v]||''}">${icons[v]||""} ${v}</span>`;
}
function dirBadge(v){
  if(!v||v==="N/A") return "—";
  let cls="dir-sd";
  if(v.includes("STRONG UP"))  cls="dir-sup";
  else if(v.includes("UP"))    cls="dir-up";
  else if(v.includes("DOWN"))  cls="dir-dn";
  else if(v.includes("PULL"))  cls="dir-pb";
  return `<span class="${cls}">${v}</span>`;
}
function priceBuy(v){
  if(!v||v===0||v==="") return "—";
  return `<span class="price-buy">RM ${parseFloat(v).toFixed(3)}</span>`;
}
function priceSell(v){
  if(!v||v===0||v==="") return "—";
  return `<span class="price-sell">RM ${parseFloat(v).toFixed(3)}</span>`;
}
function priceSL(v){
  if(!v||v===0||v==="") return "—";
  return `<span class="price-sl">RM ${parseFloat(v).toFixed(3)}</span>`;
}
function rrBadge(v){
  if(!v||v===0||v==="") return "—";
  const n=parseFloat(v);
  const cls=n>=3?"rr-good":n>=2?"rr-ok":"rr-bad";
  const icon=n>=3?"🏆":n>=2?"✅":"⚠️";
  return `<span class="${cls}">${icon} ${n.toFixed(2)}x</span>`;
}
function confBadge(v){
  if(!v||v==="") return "—";
  const n=parseFloat(v);
  const cls=n>=70?"conf-high":n>=55?"conf-mid":"conf-low";
  return `<span class="${cls}">${n.toFixed(1)}%</span>`;
}
// ── TRADER PRO BADGE ──────────────────────────────────────
function traderProBadge(v){
  if(!v||v==="N/A") return "—";
  let cls="tp-sk";
  if(v.includes("STRONG BUY")) cls="tp-sb";
  else if(v.includes("BUY"))   cls="tp-bl";
  else if(v.includes("ALERT")) cls="tp-al";
  else if(v.includes("WAIT"))  cls="tp-wp";
  else if(v.includes("MONITOR")) cls="tp-mn";
  else if(v.includes("WATCH")) cls="tp-wl";
  else if(v.includes("ABORT")) cls="tp-ab";
  else if(v.includes("OVER"))  cls="tp-ov";
  else if(v.includes("SKIP"))  cls="tp-sk";
  return `<span class="${cls}">${v}</span>`;
}

// ── ROBOT ALGO BADGE — sama CSS dengan Trader Pro ────────
function robotAlgoBadge(v){
  if(!v||v==="N/A") return "—";
  let cls="tp-sk";
  if(v.includes("STRONG BUY")) cls="tp-sb";
  else if(v.includes("BUY"))   cls="tp-bl";
  else if(v.includes("ALERT")) cls="tp-al";
  else if(v.includes("WAIT"))  cls="tp-wp";
  else if(v.includes("MONITOR")) cls="tp-mn";
  else if(v.includes("WATCH")) cls="tp-wl";
  else if(v.includes("ABORT")) cls="tp-ab";
  else if(v.includes("OVER"))  cls="tp-ov";
  else if(v.includes("SKIP"))  cls="tp-sk";
  return `<span class="${cls}">${v}</span>`;
}

// ── MARKET BANNER ─────────────────────────────────────────
function updateMarketBanner(dir, pct){
  const banner=document.getElementById("mktBanner");
  const card  =document.getElementById("mktCard");
  if(!dir||dir==="NEUTRAL") return;
  let bg="#21262d", color="#e6edf3", border="#30363d";
  if(dir.includes("BULLISH MARKET")){
    bg="#0d2d1a"; color="#56d364"; border="#1a4731";
  }else if(dir.includes("MILD BULLISH")){
    bg="#1a3a1a"; color="#3fb950"; border="#2a5a2a";
  }else if(dir.includes("NEUTRAL")){
    bg="#3d2f00"; color="#d29922"; border="#5a4500";
  }else if(dir.includes("MILD BEARISH")){
    bg="#3d1a00"; color="#ffa657"; border="#5a2a00";
  }else if(dir.includes("BEARISH")){
    bg="#5a0000"; color="#ff7b72"; border="#8a0000";
  }
  banner.style.display="block";
  banner.style.background=bg;
  banner.style.color=color;
  banner.style.borderColor=border;
  banner.innerHTML=
    `📊 MALAYSIA MARKET: <strong>${dir}</strong> &nbsp;|&nbsp;`+
    `Bullish: <strong>${pct}%</strong> &nbsp;|&nbsp;`+
    `<small style="opacity:0.8">Berdasarkan `+
    `${allData[currentTab]?.length||0} saham</small>`;
  card.style.background=bg;
  card.style.borderColor=border;
  document.getElementById("sMktDir").textContent=dir;
  document.getElementById("sMktDir").style.color=color;
  document.getElementById("sMktPct").textContent=pct+"%";
  document.getElementById("sMktPct").style.color=color;
}

// ── STANDARD BADGES ───────────────────────────────────────
function techBadge(v){
  const m={"Strong Buy":"b-sb","Buy":"b-b","Neutral":"b-n",
            "Sell":"b-s","Strong Sell":"b-ss"};
  return `<span class="badge ${m[v]||''}">${v||'N/A'}</span>`;
}
function rsiBadge(v){
  const m={"Sweet Spot":"b-sw","Bullish":"b-bu","Overbought":"b-ob",
            "Extreme OB":"b-ob","Bearish":"b-s","Oversold":"b-os"};
  return `<span class="badge ${m[v]||''}">${v||'N/A'}</span>`;
}
function emaBadge(v){
  const m={"Perfect Bull":"b-pb","Partial Bull":"b-pa",
            "Mixed":"b-mx","Perfect Bear":"b-br"};
  return `<span class="badge ${m[v]||''}">${v||'N/A'}</span>`;
}
function macdBadge(v){
  const m={"Bull+Zero":"b-bz","Bull-Zero":"b-bm",
            "Bear+Zero":"b-rz","Bear-Zero":"b-rm"};
  return `<span class="badge ${m[v]||''}">${v||'N/A'}</span>`;
}
function gradeBadge(v){
  const m={"A+":"g-ap","A":"g-a","B+":"g-bp","B":"g-b","C":"g-c","D":"g-d"};
  const i={"A+":"🏆","A":"⭐","B+":"✅","B":"👍","C":"➖","D":"❌"};
  return `<span class="badge ${m[v]||''}">${i[v]||''} ${v||'N/A'}</span>`;
}
function scoreBar(s){
  const p=Math.min(s,100);
  const c=s>=75?"#56d364":s>=55?"#d29922":"#f85149";
  return `<div class="score-bar">
    <div class="score-fill" style="width:${p*0.7}px;background:${c}"></div>
    <span class="score-num" style="color:${c}">${s}</span>
  </div>`;
}
function chgCell(v){
  if(v===""||v===null) return "—";
  const n=parseFloat(v);
  return `<span class="${n>=0?'chg-p':'chg-n'}">`+
         `${n>=0?'+':''}${n.toFixed(2)}%</span>`;
}
function fmtNum(v,d=2){
  if(v===""||v===null||v===undefined) return "—";
  const n=parseFloat(v);
  return isNaN(n)?"—":n.toFixed(d);
}
function fmtVol(v){
  if(!v) return "—";
  const n=parseFloat(v);
  if(n>=1e9) return (n/1e9).toFixed(1)+"B";
  if(n>=1e6) return (n/1e6).toFixed(1)+"M";
  if(n>=1e3) return (n/1e3).toFixed(0)+"K";
  return n.toFixed(0);
}
function fmtCap(v){
  if(!v) return "—";
  const n=parseFloat(v);
  if(n>=1e9) return "RM"+(n/1e9).toFixed(2)+"B";
  if(n>=1e6) return "RM"+(n/1e6).toFixed(1)+"M";
  return "RM"+n.toFixed(0);
}

// ── TAB SWITCH ────────────────────────────────────────────
function switchTab(tab) {
  // ── Kalau dalam search mode, clear dulu ──────────────────
  if (isSearchMode) {
    clearSearch();
  }

  currentTab = tab;
  document.querySelectorAll(".tab-btn")
          .forEach(b => b.classList.remove("active"));
  document.getElementById("tab-" + tab).classList.add("active");

  if (allData[tab]) renderTable(allData[tab], tab === "best");
  else              loadData();
}

// ── LOAD DATA ─────────────────────────────────────────────
async function loadData() {
  // ── Kalau dalam search mode, exit dulu ───────────────────
  if (isSearchMode) exitSearchMode();

  // ... (baki code loadData() yang sedia ada, TIDAK berubah)
  const btn = document.getElementById("refreshBtn");
  btn.disabled = true;
  btn.textContent = "⏳ Loading...";
  showLoading();
  try{
    const url=currentTab==="best"
      ?"/api/best"
      :"/api/screener/"+currentTab;
    const res =await fetch(url);
    const json=await res.json();
    if(json.status!=="ok")
      throw new Error(json.message||"API error");
    allData[currentTab]=json.data;
    document.getElementById("lastUpdated").innerHTML=
      `🕐 Updated: ${json.updated}<br>📡      TradingView Malaysia`;
    if(json.market_direction){
      updateMarketBanner(json.market_direction, json.market_pct||0);
    }
    renderTable(json.data, currentTab==="best");
    updateStats(json.data);
    populateSectors(json.data);
  }catch(e){
    showEmpty();
    console.error(e);
    alert("❌ Error: "+e.message);
  }finally{
    btn.disabled=false;
    btn.textContent="🔄 Refresh Data";
  }
}

// ── QUALITY FILTER ────────────────────────────────────────
function applyQualityFilter(data){
  return data.filter(r=>{
    if(["D","C"].includes(r.Grade))                            return false;
    if(["Extreme OB"].includes(r.RSI_Zone))                    return false;
    if(!["Perfect Bull","Partial Bull"].includes(r.EMA_Trend)) return false;
    if(!["Bull+Zero","Bull-Zero"].includes(r.MACD_Label))      return false;
    if(!["Strong Buy","Buy"].includes(r.Tech_Signal))          return false;
    if((parseFloat(r.Score)||0)<50)                            return false;
    return true;
  });
}

// ── RENDER TABLE ──────────────────────────────────────────
// ── RENDER TABLE ──────────────────────────────────────────
function renderTable(data, isBest=false){
  if(!data||data.length===0){showEmpty();return;}
  data=applyQualityFilter(data);
  if(data.length===0){showEmpty();return;}

  data.sort((a,b)=>{
    let va=a[sortCol]??0, vb=b[sortCol]??0;
    if(typeof va==="string") va=va.toLowerCase();
    if(typeof vb==="string") vb=vb.toLowerCase();
    return va<vb?sortDir:va>vb?-sortDir:0;
  });

  // ── 6 Kolum Utama — Key Indicators ───────────────────────
  const KEY_COLS = new Set([
    "Robot_Algo","Trader_Pro","Score","Grade","RR_Ratio","EW_Wave"
  ]);

  // ── Column Definitions ────────────────────────────────────
  const cols=isBest?[
    {k:"Symbol",     l:"Symbol"},
    {k:"Company",    l:"Syarikat"},
    {k:"Sector",     l:"Sektor"},
    {k:"TF_Count",   l:"TF"},
    {k:"In_Monthly", l:"M"},
    {k:"In_Weekly",  l:"W"},
    {k:"In_Daily",   l:"D"},
    {k:"In_4H",      l:"4H"},
    {k:"In_1H",      l:"1H"},
    {k:"In_15Min",   l:"15M"},
    {k:"In_5Min",    l:"5M"},
    {k:"Score",      l:"Score"},
    {k:"Grade",      l:"Grade"},
    {k:"Price",      l:"Price"},
    {k:"Buy_Price",  l:"💚 Buy"},
    {k:"Sell_Price", l:"🔴 Sell"},
    {k:"Stop_Loss",  l:"⚠️ SL"},
    {k:"RR_Ratio",   l:"R:R"},
    {k:"Chg_Pct",    l:"Chg%"},
    {k:"Trader_Pro", l:"🧠 Trader Pro"},
    {k:"Robot_Algo", l:"🤖 Robot Algo"},
    {k:"EW_Wave",    l:"EW Wave"},
    {k:"Direction",  l:"Direction"},
    {k:"Confidence", l:"EW Signal%"},
    {k:"Volume",     l:"Volume"},
    {k:"Market_Cap", l:"Mkt Cap"},
    {k:"Tech_Signal",l:"Tech"},
    {k:"RSI_Zone",   l:"RSI Zone"},
    {k:"RSI",        l:"RSI"},
    {k:"Stoch_K",    l:"Stoch K"},
    {k:"EMA_Trend",  l:"EMA Trend"},
    {k:"MACD_Label", l:"MACD"},
    {k:"Fib_382",    l:"Fib 38.2%"},
    {k:"Fib_618",    l:"Fib 61.8%"},
    {k:"High_52W",   l:"52W Hi"},
    {k:"Low_52W",    l:"52W Lo"},
    {k:"PE",         l:"P/E"},
    {k:"ROE",        l:"ROE%"},
    {k:"Net_Margin", l:"Net Mgn%"},
    {k:"DE_Ratio",   l:"D/E"},
    {k:"Rev_Growth", l:"Rev Grw%"},
    {k:"Div_Yield",  l:"Div%"},
  ]:[
    {k:"Symbol",      l:"Symbol"},
    {k:"Company",     l:"Syarikat"},
    {k:"Sector",      l:"Sektor"},
    {k:"Score",       l:"Score"},
    {k:"Grade",       l:"Grade"},
    {k:"Price",       l:"Price"},
    {k:"Buy_Price",   l:"💚 Buy"},
    {k:"Sell_Price",  l:"🔴 Sell"},
    {k:"Stop_Loss",   l:"⚠️ SL"},
    {k:"RR_Ratio",    l:"R:R"},
    {k:"Chg_Pct",     l:"Chg%"},
    {k:"Trader_Pro",  l:"🧠 Trader Pro"},
    {k:"Robot_Algo",  l:"🤖 Robot Algo"},
    {k:"Volume",      l:"Volume"},
    {k:"Avg_Vol",     l:"Avg Vol"},
    {k:"Market_Cap",  l:"Mkt Cap"},
    {k:"Tech_Signal", l:"Tech"},
    {k:"RSI_Zone",    l:"RSI Zone"},
    {k:"RSI",         l:"RSI"},
    {k:"EMA_Trend",   l:"EMA Trend"},
    {k:"MACD_Label",  l:"MACD"},
    {k:"Stoch_K",     l:"Stoch K"},
    {k:"EPS",         l:"EPS"},
    {k:"PE",          l:"P/E"},
    {k:"PB",          l:"P/B"},
    {k:"ROE",         l:"ROE%"},
    {k:"ROA",         l:"ROA%"},
    {k:"Net_Margin",  l:"Net Mgn%"},
    {k:"Gross_Margin",l:"Gross Mgn%"},
    {k:"DE_Ratio",    l:"D/E"},
    {k:"CR",          l:"Curr R"},
    {k:"Rev_Growth",  l:"Rev Grw%"},
    {k:"Div_Yield",   l:"Div%"},
    {k:"Fib_382",     l:"Fib 38.2%"},
    {k:"Fib_618",     l:"Fib 61.8%"},
    {k:"High_52W",    l:"52W Hi"},
    {k:"Low_52W",     l:"52W Lo"},
  ];

  // ── Build Header ──────────────────────────────────────────
  let hHtml="<tr>";
  cols.forEach(c=>{
    const sortCls = sortCol===c.k?(sortDir===-1?"sort-desc":"sort-asc"):"";
    const keyCls  = KEY_COLS.has(c.k) ? " th-key" : "";
    const label   = KEY_COLS.has(c.k) ? "⭐ "+c.l : c.l;
    hHtml+=`<th class="${sortCls}${keyCls}"
              onclick="sortBy('${c.k}')">${label}</th>`;
  });
  hHtml+="</tr>";
  document.getElementById("tableHead").innerHTML=hHtml;

  // ── Build Body ────────────────────────────────────────────
  let bHtml="";
  data.forEach(r=>{
    bHtml+="<tr>";
    cols.forEach(c=>{
      const v    = r[c.k];
      const tdKy = KEY_COLS.has(c.k) ? " td-key" : "";
      let cell   = "";

      if(c.k==="Symbol"){
        cell=`<td class="left symbol"
                onclick="openChart('${v}')">${v}</td>`;

      }else if(c.k==="Company"||c.k==="Sector"){
        cell=`<td class="left"
                style="max-width:160px;overflow:hidden;
                       text-overflow:ellipsis"
                title="${v||''}">${v||'—'}</td>`;

      }else if(c.k==="Tech_Signal")
        cell=`<td class="${tdKy}">${techBadge(v)}</td>`;
      else if(c.k==="RSI_Zone")
        cell=`<td class="${tdKy}">${rsiBadge(v)}</td>`;
      else if(c.k==="EMA_Trend")
        cell=`<td class="${tdKy}">${emaBadge(v)}</td>`;
      else if(c.k==="MACD_Label")
        cell=`<td class="${tdKy}">${macdBadge(v)}</td>`;
      else if(c.k==="Grade")
        cell=`<td class="${tdKy}">${gradeBadge(v)}</td>`;
      else if(c.k==="Score")
        cell=`<td class="${tdKy}">${scoreBar(v||0)}</td>`;
      else if(c.k==="Chg_Pct")
        cell=`<td class="${tdKy}">${chgCell(v)}</td>`;
      else if(c.k==="Volume"||c.k==="Avg_Vol")
        cell=`<td class="${tdKy}">${fmtVol(v)}</td>`;
      else if(c.k==="Market_Cap")
        cell=`<td class="${tdKy}">${fmtCap(v)}</td>`;
      else if(c.k==="Trader_Pro")
        cell=`<td class="${tdKy}">${traderProBadge(v)}</td>`;
      else if(c.k==="Robot_Algo")
        cell=`<td class="${tdKy}">${robotAlgoBadge(v)}</td>`;
      else if(c.k==="EW_Wave")
        cell=`<td class="${tdKy}">${ewBadge(v)}</td>`;
      else if(c.k==="Direction")
        cell=`<td class="${tdKy}">${dirBadge(v)}</td>`;
      else if(c.k==="Confidence")
        cell=`<td class="${tdKy}">${confBadge(v)}</td>`;
      else if(c.k==="Buy_Price")
        cell=`<td class="${tdKy}">${priceBuy(v)}</td>`;
      else if(c.k==="Sell_Price")
        cell=`<td class="${tdKy}">${priceSell(v)}</td>`;
      else if(c.k==="Stop_Loss")
        cell=`<td class="${tdKy}">${priceSL(v)}</td>`;
      else if(c.k==="RR_Ratio")
        cell=`<td class="${tdKy}">${rrBadge(v)}</td>`;
      else if(c.k==="Fib_382"||c.k==="Fib_618")
        cell=`<td class="${tdKy}"
                style="color:#d2a8ff;font-size:11px">
                RM ${fmtNum(v,3)}</td>`;
      else if(c.k==="In_Monthly"||c.k==="In_Weekly"||
              c.k==="In_Daily"  ||c.k==="In_4H"    ||
              c.k==="In_1H"     ||c.k==="In_15Min"  ||
              c.k==="In_5Min"){
        const yes=v===true||v==="True"||v==="true";
        cell=`<td class="${yes?'tf-y':'tf-n'}${tdKy}">
                ${yes?'✅':'—'}</td>`;
      }else if(c.k==="TF_Count"){
        const n=parseInt(v||0);
        const color=n===TOTAL_TF?"#ffd700":
                    n>=5?"#56d364":
                    n>=3?"#3fb950":"#8b949e";
        cell=`<td class="${tdKy}"
                style="color:${color};font-weight:700">
                ${n}/${TOTAL_TF}</td>`;
      }else{
        cell=`<td class="${tdKy}">${fmtNum(v)}</td>`;
      }

      bHtml+=cell;
    });
    bHtml+="</tr>";
  });

  document.getElementById("tableBody").innerHTML=bHtml;
  document.getElementById("loadingDiv").style.display="none";
  document.getElementById("emptyDiv").style.display="none";
  document.getElementById("tableDiv").style.display="block";
  document.getElementById("countBadge").textContent=data.length+" stocks";
}
// ── SORT ──────────────────────────────────────────────────
function sortBy(c){
  if(sortCol===c) sortDir*=-1;
  else{ sortCol=c; sortDir=-1; }
  const d=allData[currentTab];
  if(d) renderTable(d, currentTab==="best");
}

// ── FILTER TABLE — dengan search mode guard ───────────────
function filterTable() {
  // Guard — kalau dalam search mode, jangan filter
  if (isSearchMode) return;

  const s   = document.getElementById("searchBox").value.toLowerCase();
  const g   = document.getElementById("gradeFilter").value;
  const sec = document.getElementById("sectorFilter").value;
  const ema = document.getElementById("emaFilter").value;
  const d   = allData[currentTab] || [];

  const f = d.filter(r => {
    if (["D","C"].includes(r.Grade))                             return false;
    if (["Extreme OB"].includes(r.RSI_Zone))                     return false;
    if (!["Perfect Bull","Partial Bull"].includes(r.EMA_Trend))  return false;
    if (!["Bull+Zero","Bull-Zero"].includes(r.MACD_Label))       return false;
    if (!["Strong Buy","Buy"].includes(r.Tech_Signal))           return false;
    if ((parseFloat(r.Score) || 0) < 50)                         return false;

    const ms  = !s   || (r.Symbol  || "").toLowerCase().includes(s)
                     || (r.Company || "").toLowerCase().includes(s);
    const mg  = !g   || (r.Grade     || "") === g;
    const msc = !sec || (r.Sector    || "") === sec;
    const me  = !ema || (r.EMA_Trend || "") === ema;

    return ms && mg && msc && me;
  });

  renderTable(f, currentTab === "best");
}

// ── STATS ─────────────────────────────────────────────────
function updateStats(data){
  if(!data||!data.length) return;
  const filtered=data.filter(r=>{
    if(["D","C"].includes(r.Grade))                            return false;
    if(["Extreme OB"].includes(r.RSI_Zone))                    return false;
    if(!["Perfect Bull","Partial Bull"].includes(r.EMA_Trend)) return false;
    if(!["Bull+Zero","Bull-Zero"].includes(r.MACD_Label))      return false;
    if(!["Strong Buy","Buy"].includes(r.Tech_Signal))          return false;
    if((parseFloat(r.Score)||0)<50)                            return false;
    return true;
  });

  document.getElementById("sTotal").textContent=filtered.length;
  document.getElementById("sGradeA").textContent=
    filtered.filter(r=>r.Grade==="A+"||r.Grade==="A").length;
  // ✅ FIX — Best = muncul dalam SEMUA 7 TF
  document.getElementById("sBest").textContent=
    filtered.filter(r=>parseInt(r.TF_Count||0)===TOTAL_TF).length;
  document.getElementById("sPositive").textContent=
    filtered.filter(r=>parseFloat(r.Chg_Pct||0)>0).length;

  const avg=filtered.length>0
    ?filtered.reduce((s,r)=>s+(parseFloat(r.Score)||0),0)/filtered.length
    :0;
  document.getElementById("sAvg").textContent=avg.toFixed(1);

  const upCount=filtered.filter(r=>
    r.Direction&&r.Direction.includes("UP")).length;
  const upPct=filtered.length>0
    ?Math.round(upCount/filtered.length*100):0;

  let mktDir="⚪ NEUTRAL/SIDEWAYS";
    if(upPct>=70)      mktDir="🟢 BULLISH MARKET";
  else if(upPct>=55) mktDir="🟡 MILD BULLISH";
  else if(upPct>=45) mktDir="⚪ NEUTRAL/SIDEWAYS";
  else if(upPct>=30) mktDir="🟠 MILD BEARISH";
  else               mktDir="🔴 BEARISH MARKET";

  updateMarketBanner(mktDir, upPct);
}

// ── SECTORS ───────────────────────────────────────────────
function populateSectors(data){
  const filtered=data.filter(r=>
    !["D","C"].includes(r.Grade)&&
    ["Perfect Bull","Partial Bull"].includes(r.EMA_Trend)
  );
  const secs=[...new Set(
    filtered.map(r=>r.Sector).filter(Boolean)
  )].sort();
  const sel=document.getElementById("sectorFilter");
  const cur=sel.value;
  sel.innerHTML='<option value="">Semua Sektor</option>';
  secs.forEach(s=>sel.innerHTML+=
    `<option value="${s}" ${s===cur?"selected":""}>${s}</option>`);
}

// ── OPEN CHART ────────────────────────────────────────────
function openChart(sym){
  window.open(
    "https://www.tradingview.com/chart/?symbol=MYX:"+sym,
    "_blank"
  );
}

// ── SHOW STATES ───────────────────────────────────────────
function showLoading(){
  document.getElementById("loadingDiv").style.display="block";
  document.getElementById("loadingDiv").innerHTML=
    `<div style="text-align:center;padding:60px">
      <div class="spinner"></div>
      <div style="margin-top:15px;color:#8b949e">
        Mengambil data dari TradingView...<br>
        <small>Menapis saham bullish berkualiti + Elliott Wave...</small>
      </div>
    </div>`;
  document.getElementById("tableDiv").style.display="none";
  document.getElementById("emptyDiv").style.display="none";
}

function showEmpty(){
  document.getElementById("loadingDiv").style.display="none";
  document.getElementById("tableDiv").style.display="none";
  document.getElementById("emptyDiv").style.display="block";
}

// ── KEYBOARD SHORTCUTS ────────────────────────────────────
// ✅ FIX — shortcut dikemaskini ikut tab baharu
document.addEventListener("keydown", e=>{
  if(e.key==="F5"){ e.preventDefault(); loadData(); }
  if(e.altKey&&e.key==="1") switchTab("monthly");
  if(e.altKey&&e.key==="2") switchTab("weekly");
  if(e.altKey&&e.key==="3") switchTab("daily");
  if(e.altKey&&e.key==="4") switchTab("4h");
  if(e.altKey&&e.key==="5") switchTab("1h");
  if(e.altKey&&e.key==="6") switchTab("15m");
  if(e.altKey&&e.key==="7") switchTab("5m");
  if(e.altKey&&e.key==="8") switchTab("best");
});

// ════════════════════════════════════════════════════════════
// UNIVERSAL SEARCH ENGINE
// ════════════════════════════════════════════════════════════

let searchDebounceTimer = null;
let isSearchMode        = false;
let lastSearchQuery     = "";

// ── Threshold: berapa karakter sebelum trigger live search ──
const SEARCH_TRIGGER_LEN = 2;

// ── Debounce delay (ms) ──────────────────────────────────────
const SEARCH_DEBOUNCE_MS = 600;

/**
 * Dipanggil setiap kali user menaip dalam search box.
 * Logik:
 *   < SEARCH_TRIGGER_LEN chars → filter biasa (dalam list)
 *   >= SEARCH_TRIGGER_LEN chars → debounce → live TradingView search
 */
function onSearchInput(val) {
  const clearBtn = document.getElementById("clearBtn");
  clearBtn.classList.toggle("show", val.length > 0);

  // Batal timer lama
  clearTimeout(searchDebounceTimer);

  if (val.length === 0) {
    // Kosong → kembali ke screener biasa
    exitSearchMode();
    filterTable();
    return;
  }

  if (val.length < SEARCH_TRIGGER_LEN) {
    // Terlalu pendek → filter biasa sahaja
    if (isSearchMode) exitSearchMode();
    filterTable();
    return;
  }

  // Debounce — tunggu user berhenti menaip
  searchDebounceTimer = setTimeout(() => {
    triggerUniversalSearch(val.trim());
  }, SEARCH_DEBOUNCE_MS);
}

/**
 * Tekan Enter → search serta-merta tanpa tunggu debounce
 */
function onSearchKeydown(event) {
  if (event.key === "Enter") {
    clearTimeout(searchDebounceTimer);
    const val = event.target.value.trim();
    if (val.length >= SEARCH_TRIGGER_LEN) {
      triggerUniversalSearch(val);
    }
  }
  if (event.key === "Escape") {
    clearSearch();
  }
}

/**
 * Hantar request ke /api/search/<symbol>
 * Papar hasil TANPA quality filter
 */
async function triggerUniversalSearch(query) {
  if (query === lastSearchQuery && isSearchMode) return; // Elak duplicate
  lastSearchQuery = query;

  console.log(`[SEARCH] Query: "${query}"`);

  // ── Tunjuk loading state ──────────────────────────────────
  showSearchLoading(query);

  try {
    const res  = await fetch(`/api/search/${encodeURIComponent(query)}`);
    const json = await res.json();

    if (json.status !== "ok") throw new Error(json.message || "Search error");

    console.log(`[SEARCH] Ditemui: ${json.count} kaunter`);

    // ── Masuk search mode ─────────────────────────────────
    enterSearchMode(query, json.data, json.count);

  } catch (e) {
    console.error("[SEARCH] Error:", e);
    showSearchError(query, e.message);
  }
}

/**
 * Aktifkan Search Mode UI
 */
function enterSearchMode(query, data, count) {
  isSearchMode = true;

  // Update UI indicators
  document.getElementById("searchModeBadge").classList.add("active");
  document.getElementById("searchInfoBar").classList.add("show");
  document.getElementById("searchQueryLabel").textContent = query;
  document.getElementById("searchSpinner").classList.remove("show");

  // Disable filter dropdowns semasa search mode
  document.getElementById("gradeFilter").disabled  = true;
  document.getElementById("sectorFilter").disabled = true;
  document.getElementById("emaFilter").disabled     = true;

  if (!data || data.length === 0) {
    showSearchEmpty(query);
    return;
  }

  // ── Render table TANPA quality filter ────────────────────
  renderSearchTable(data, query);

  // Update count badge
  document.getElementById("countBadge").textContent =
    `${count} kaunter ditemui`;
  document.getElementById("countBadge").style.background = "#2d1b69";
  document.getElementById("countBadge").style.color      = "#d2a8ff";
}

/**
 * Keluar dari Search Mode — kembali ke screener biasa
 */
function exitSearchMode() {
  isSearchMode    = false;
  lastSearchQuery = "";

  document.getElementById("searchModeBadge").classList.remove("active");
  document.getElementById("searchInfoBar").classList.remove("show");
  document.getElementById("searchSpinner").classList.remove("show");

  // Re-enable filter dropdowns
  document.getElementById("gradeFilter").disabled  = false;
  document.getElementById("sectorFilter").disabled = false;
  document.getElementById("emaFilter").disabled     = false;

  // Reset count badge style
  document.getElementById("countBadge").style.background = "";
  document.getElementById("countBadge").style.color      = "";
}

/**
 * Clear button — kosongkan search & kembali ke screener
 */
function clearSearch() {
  document.getElementById("searchBox").value = "";
  document.getElementById("clearBtn").classList.remove("show");
  clearTimeout(searchDebounceTimer);
  exitSearchMode();

  // Re-render screener data asal
  const d = allData[currentTab];
  if (d) renderTable(d, currentTab === "best");
  else   showLoading();
}

/**
 * Tunjuk spinner semasa fetch
 */
function showSearchLoading(query) {
  document.getElementById("searchSpinner").classList.add("show");
  document.getElementById("searchModeBadge").classList.add("active");

  // Tunjuk loading dalam table area
  document.getElementById("loadingDiv").style.display  = "block";
  document.getElementById("loadingDiv").innerHTML = `
    <div style="text-align:center;padding:40px">
      <div class="spinner"></div>
      <div style="margin-top:15px;color:#d2a8ff">
        🔍 Mencari "<strong>${query}</strong>" dari TradingView...<br>
        <small style="color:#8b949e">
          Mengambil data langsung — ini mungkin mengambil masa 3-5 saat
        </small>
      </div>
    </div>`;
  document.getElementById("tableDiv").style.display   = "none";
  document.getElementById("emptyDiv").style.display   = "none";
}

/**
 * Render table khusus untuk search results
 * PERBEZAAN: Tidak apply quality filter, ada row highlight purple
 */
function renderSearchTable(data, query) {
  if (!data || data.length === 0) {
    showSearchEmpty(query);
    return;
  }

  // ── Column definitions untuk search result ────────────────
  const cols = [
    { k: "Symbol",      l: "Symbol"       },
    { k: "Company",     l: "Syarikat"     },
    { k: "Sector",      l: "Sektor"       },
    { k: "Score",       l: "Score"        },
    { k: "Grade",       l: "Grade"        },
    { k: "Price",       l: "Price (RM)"   },
    { k: "Buy_Price",   l: "💚 Buy"       },
    { k: "Sell_Price",  l: "🔴 Sell"      },
    { k: "Stop_Loss",   l: "⚠️ SL"        },
    { k: "RR_Ratio",    l: "R:R"          },
    { k: "Chg_Pct",     l: "Chg%"         },
    { k: "Trader_Pro",  l: "🧠 Trader Pro"},
    { k: "Robot_Algo",  l: "🤖 Robot Algo"},
    { k: "EW_Wave",     l: "EW Wave"      },
    { k: "Direction",   l: "Direction"    },
    { k: "Confidence",  l: "EW Signal%"   },
    { k: "Volume",      l: "Volume"       },
    { k: "Market_Cap",  l: "Mkt Cap"      },
    { k: "Tech_Signal", l: "Tech"         },
    { k: "RSI_Zone",    l: "RSI Zone"     },
    { k: "RSI",         l: "RSI"          },
    { k: "EMA_Trend",   l: "EMA Trend"    },
    { k: "MACD_Label",  l: "MACD"         },
    { k: "Stoch_K",     l: "Stoch K"      },
    { k: "EPS",         l: "EPS"          },
    { k: "PE",          l: "P/E"          },
    { k: "PB",          l: "P/B"          },
    { k: "ROE",         l: "ROE%"         },
    { k: "ROA",         l: "ROA%"         },
    { k: "Net_Margin",  l: "Net Mgn%"     },
    { k: "DE_Ratio",    l: "D/E"          },
    { k: "Rev_Growth",  l: "Rev Grw%"     },
    { k: "Div_Yield",   l: "Div%"         },
    { k: "Fib_382",     l: "Fib 38.2%"   },
    { k: "Fib_618",     l: "Fib 61.8%"   },
    { k: "High_52W",    l: "52W Hi"       },
    { k: "Low_52W",     l: "52W Lo"       },
  ];

  // ── Build Header ──────────────────────────────────────────
  let hHtml = "<tr>";
  cols.forEach(c => {
    hHtml += `<th style="background:#2d1b69;color:#d2a8ff">${c.l}</th>`;
  });
  hHtml += "</tr>";
  document.getElementById("tableHead").innerHTML = hHtml;

  // ── Build Body ────────────────────────────────────────────
  let bHtml = "";
  data.forEach(r => {
    // Highlight row — purple untuk search result
    bHtml += `<tr class="search-result-row">`;

    cols.forEach(c => {
      const v = r[c.k];
      let cell = "";

      if (c.k === "Symbol") {
        // Tambah badge [SEARCH] pada symbol
        cell = `<td class="left symbol" onclick="openChart('${v}')">
                  ${v || "—"}
                  <span class="is-search-badge">SEARCH</span>
                </td>`;

      } else if (c.k === "Company" || c.k === "Sector") {
        cell = `<td class="left"
                  style="max-width:160px;overflow:hidden;
                         text-overflow:ellipsis"
                  title="${v || ''}">${v || "—"}</td>`;

      } else if (c.k === "Tech_Signal")  cell = `<td>${techBadge(v)}</td>`;
      else if (c.k === "RSI_Zone")       cell = `<td>${rsiBadge(v)}</td>`;
      else if (c.k === "EMA_Trend")      cell = `<td>${emaBadge(v)}</td>`;
      else if (c.k === "MACD_Label")     cell = `<td>${macdBadge(v)}</td>`;
      else if (c.k === "Grade")          cell = `<td>${gradeBadge(v)}</td>`;
      else if (c.k === "Score")          cell = `<td>${scoreBar(v || 0)}</td>`;
      else if (c.k === "Chg_Pct")        cell = `<td>${chgCell(v)}</td>`;
      else if (c.k === "Volume" ||
               c.k === "Avg_Vol")        cell = `<td>${fmtVol(v)}</td>`;
      else if (c.k === "Market_Cap")     cell = `<td>${fmtCap(v)}</td>`;
      else if (c.k === "Trader_Pro")     cell = `<td>${traderProBadge(v)}</td>`;
      else if (c.k === "Robot_Algo")     cell = `<td>${robotAlgoBadge(v)}</td>`;
      else if (c.k === "EW_Wave")        cell = `<td>${ewBadge(v)}</td>`;
      else if (c.k === "Direction")      cell = `<td>${dirBadge(v)}</td>`;
      else if (c.k === "Confidence")     cell = `<td>${confBadge(v)}</td>`;
      else if (c.k === "Buy_Price")      cell = `<td>${priceBuy(v)}</td>`;
      else if (c.k === "Sell_Price")     cell = `<td>${priceSell(v)}</td>`;
      else if (c.k === "Stop_Loss")      cell = `<td>${priceSL(v)}</td>`;
      else if (c.k === "RR_Ratio")       cell = `<td>${rrBadge(v)}</td>`;
      else if (c.k === "Fib_382" ||
               c.k === "Fib_618")
        cell = `<td style="color:#d2a8ff;font-size:11px">
                  RM ${fmtNum(v, 3)}</td>`;
      else if (c.k === "Price")
        cell = `<td style="color:#e6edf3;font-weight:700">
                  RM ${fmtNum(v, 3)}</td>`;
      else {
        cell = `<td>${fmtNum(v)}</td>`;
      }

      bHtml += cell;
    });

    bHtml += "</tr>";
  });

  document.getElementById("tableBody").innerHTML  = bHtml;
  document.getElementById("loadingDiv").style.display = "none";
  document.getElementById("emptyDiv").style.display   = "none";
  document.getElementById("tableDiv").style.display   = "block";
}

/**
 * Tunjuk empty state khusus untuk search
 */
function showSearchEmpty(query) {
  document.getElementById("searchSpinner").classList.remove("show");
  document.getElementById("loadingDiv").style.display = "none";
  document.getElementById("tableDiv").style.display   = "none";
  document.getElementById("emptyDiv").style.display   = "block";
  document.getElementById("emptyDiv").innerHTML = `
    <div style="font-size:48px">🔍</div>
    <div style="margin-top:15px;color:#d2a8ff;font-size:16px">
      Tiada kaunter ditemui untuk "<strong>${query}</strong>"
    </div>
    <div style="margin-top:10px;font-size:12px;color:#8b949e">
      Cuba taip:<br>
      • Symbol penuh — contoh: <code style="color:#58a6ff">TENAGA</code>,
        <code style="color:#58a6ff">MAYBANK</code>,
        <code style="color:#58a6ff">PBBANK</code><br>
      • Nama syarikat — contoh: <code style="color:#58a6ff">PETRONAS</code>,
        <code style="color:#58a6ff">CIMB</code>
    </div>
    <button onclick="clearSearch()"
      style="margin-top:20px;padding:8px 20px;background:#6e40c9;
             border:none;border-radius:6px;color:#fff;
             cursor:pointer;font-size:13px">
      ← Kembali ke Screener
    </button>`;
  document.getElementById("countBadge").textContent = "0 ditemui";
}

/**
 * Tunjuk error state untuk search
 */
function showSearchError(query, errMsg) {
  document.getElementById("searchSpinner").classList.remove("show");
  document.getElementById("loadingDiv").style.display = "none";
  document.getElementById("tableDiv").style.display   = "none";
  document.getElementById("emptyDiv").style.display   = "block";
  document.getElementById("emptyDiv").innerHTML = `
    <div style="font-size:48px">⚠️</div>
    <div style="margin-top:15px;color:#f85149;font-size:15px">
      Ralat semasa mencari "<strong>${query}</strong>"
    </div>
    <div style="margin-top:8px;font-size:12px;color:#8b949e">
      ${errMsg}
    </div>
    <div style="display:flex;gap:10px;justify-content:center;margin-top:20px">
      <button onclick="triggerUniversalSearch('${query}')"
        style="padding:8px 20px;background:#238636;border:none;
               border-radius:6px;color:#fff;cursor:pointer;font-size:13px">
        🔄 Cuba Semula
      </button>
      <button onclick="clearSearch()"
        style="padding:8px 20px;background:#6e40c9;border:none;
               border-radius:6px;color:#fff;cursor:pointer;font-size:13px">
        ← Kembali ke Screener
      </button>
    </div>`;
}

// ── INIT ──────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", loadData);
setInterval(loadData, 5*60*1000);
</script>
</body>
</html>"""

# ════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  🏆 BULLISH SCREENER — Web Dashboard")
    print("=" * 55)
    print("  🌐 Dashboard  : http://localhost:5000")
    print("  🔍 Health     : http://localhost:5000/health")
    print("  📡 API Monthly: http://localhost:5000/api/screener/monthly")
    print("  📡 API Weekly : http://localhost:5000/api/screener/weekly")
    print("  📡 API Daily  : http://localhost:5000/api/screener/daily")
    print("  📡 API 4H     : http://localhost:5000/api/screener/4h")
    print("  📡 API 1H     : http://localhost:5000/api/screener/1h")
    print("  📡 API 15M    : http://localhost:5000/api/screener/15m")
    print("  📡 API 5M     : http://localhost:5000/api/screener/5m")
    print("  ⭐ API Best   : http://localhost:5000/api/best")
    # ✅ TAMBAH BARIS BARU INI
    print("  🔍 API Search : http://localhost:5000/api/search/<symbol>")
    print("  ⏹️  Stop       : Ctrl+C")
    print("=" * 55)
    print("  ✅ Timeframes Active:")
    print("     • 📆 Monthly  (1M)")
    print("     • 📅 Weekly   (1W)")
    print("     • 📊 Daily    (1D)")
    print("     • ⏱️  4 Hour   (240)")
    print("     • 🕐 1 Hour   (60)")
    print("     • ⏲️  15 Min   (15)")
    print("     • ⚡ 5 Min    (5)")
    print("=" * 55)
    print("  ✅ Filters Active:")
    print("     • Volume     > 2,000,000")
    print("     • Harga      : RM0.15 ~ RM6.00")
    print("     • RSI        : 55 ~ 75 (Sweet Spot + Mild OB)")
    print("     • EMA        : Perfect/Partial Bull")
    print("     • MACD       : Bullish")
    print("     • Signal     : Buy / Strong Buy")
    print("     • EPS        > 0")
    print("     • ROE        > 10%")
    print("     • Net Margin > 5%")
    print("     • D/E        < 1.0")
    print("     • Grade      : B, B+, A, A+ sahaja")
    print("=" * 55)
    print("  🔍 Universal Search:")
    print("     • Taip mana-mana symbol/nama syarikat")
    print("     • Contoh: TENAGA, MAYBANK, PBBANK")
    print("     • Data diambil TERUS dari TradingView")
    print("     • Tiada had — semua kaunter MYX boleh dicari")
    print("=" * 55)
    print("  ⌨️  Keyboard Shortcuts:")
    print("     • Alt+1 → Monthly")
    print("     • Alt+2 → Weekly")
    print("     • Alt+3 → Daily")
    print("     • Alt+4 → 4 Hour")
    print("     • Alt+5 → 1 Hour")
    print("     • Alt+6 → 15 Min")
    print("     • Alt+7 → 5 Min")
    print("     • Alt+8 → Best Stocks")
    print("     • F5    → Refresh")
    print("     • Esc   → Clear Search")
    print("=" * 55)
    app.run(
        host  = "0.0.0.0",
        port  = 5000,
        debug = True
    )