#!/usr/bin/env python3
"""
SYSTEM3 SIGNAL ENGINE — PRODUCTION v2.0
=========================================
Termux Android | Crypto Futures Signal System
Full Transparency Mode — ALL LOGS VISIBLE
NO HIDDEN LOGIC — NO AI/ML — NO AUTO TRADE

Architecture (LOCKED):
  1. MARKET ENVIRONMENT → HEALTHY / NEUTRAL / RISKY
  2. PAIR ANALYSIS (5m, 15m, 30m, 1h) → trend + momentum
  3. DERIVATIVES CONTEXT → BULLISH / BEARISH / NEUTRAL
  4. MARKET FLOW → AKUMULASI / DISTRIBUSI / NETRAL
  5. DECISION ENGINE → LONG / SHORT / NO TRADE

Scheduler: RUN → ANALYZE → LOG → SAVE → SEND → SLEEP (2700s)
Risk: SL 3% | TP 6% | RR 1:2
"""

import os
import sys
import json
import time
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ═══════════════════════════════════════════════════════════
# SOLUSI 1: AMBIL SYMBOL LANGSUNG DARI BINANCE (WAJIB)
# ═══════════════════════════════════════════════════════════

def get_futures_symbols() -> Set[str]:
    """Ambil daftar simbol futures yang aktif dari Binance."""
    print("  [FETCH BINANCE EXCHANGE INFO] — mengambil daftar simbol futures...")
    url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
    try:
        data = requests.get(url, timeout=30).json()
        symbols = set()
        for s in data.get("symbols", []):
            if s.get("status") == "TRADING" and s.get("contractType") == "PERPETUAL":
                symbols.add(s["symbol"])
        print(f"     → got {len(symbols)} active perpetual symbols")
        return symbols
    except Exception as e:
        print(f"     ❌ Gagal fetch exchange info: {e}")
        return set()

FUTURES_SYMBOLS = get_futures_symbols()

# ═══════════════════════════════════════════════════════════
# SOLUSI 2 + 4: VALIDASI & NORMALISASI SIMBOL
# ═══════════════════════════════════════════════════════════

def is_valid_symbol(symbol: str) -> bool:
    """Cek apakah simbol ada di daftar futures aktif."""
    return symbol in FUTURES_SYMBOLS

def normalize_symbol(input_symbol: str) -> Optional[str]:
    """
    Normalisasi simbol agar sesuai format Binance Futures.
    Contoh: PEPEUSDT → 1000PEPEUSDT, SHIBUSDT → 1000SHIBUSDT
    """
    if input_symbol in FUTURES_SYMBOLS:
        return input_symbol

    # Fallback: cari simbol yang mengandung nama input
    search = input_symbol.replace("USDT", "").replace("USDC", "")
    for sym in FUTURES_SYMBOLS:
        if search in sym and sym.endswith("USDT"):
            return sym

    return None

# ═══════════════════════════════════════════════════════════
# KONFIGURASI (LOCKED — JANGAN DIUBAH)
# ═══════════════════════════════════════════════════════════

TIMEFRAMES = ["5m", "15m", "30m", "1h"]
SLEEP_SECONDS = 2700  # 45 menit
SL_PERCENT = 3        # Stop Loss 3%
TP_PERCENT = 6        # Take Profit 6%
RR_RATIO = "1:2"      # Risk:Reward fixed

PAIR_UNIVERSE = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ADAUSDT", "DOGEUSDT", "AVAXUSDT", "SUIUSDT", "JUPUSDT",
    "INJUSDT", "ARBUSDT", "OPUSDT", "APTUSDT", "KASUSDT",
    "TIAUSDT", "SEIUSDT", "WIFUSDT", "PEPEUSDT"
]

TRENDING_COUNT_MIN = 5
TRENDING_COUNT_MAX = 10

# =========================
# SYSTEM3 CONFIG (FIXED)
# =========================

TELEGRAM_BOT_TOKEN = "ISI_TOKEN_BOT_DISINI"
TELEGRAM_CHAT_ID = "ISI_CHAT_ID_DISINI"

GITHUB_TOKEN = "ISI_GITHUB_TOKEN_DISINI"
GITHUB_REPO = "USERNAME/REPO"
GITHUB_BRANCH = "main"

GITHUB_PATH = "System3"

# ═══════════════════════════════════════════════════════════
# TERMINAL LOG UTILS (FULL TRANSPARENCY)
# ═══════════════════════════════════════════════════════════

SEPARATOR = "─" * 55
SEPARATOR_BOLD = "═" * 55

def log_header(text: str) -> None:
    print(f"\n{SEPARATOR_BOLD}")
    print(f"  {text}")
    print(SEPARATOR_BOLD)

def log_step(text: str) -> None:
    print(f"  ⚙️  {text}")

def log_info(text: str) -> None:
    print(f"     {text}")

def log_result(text: str) -> None:
    print(f"  ✅ {text}")

def log_warn(text: str) -> None:
    print(f"  ⚠️  {text}")

def log_error(text: str) -> None:
    print(f"  ❌ {text}")

def log_timestamp() -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n📅 {ts}")

# ═══════════════════════════════════════════════════════════
# HTTP SESSION + RETRY
# ═══════════════════════════════════════════════════════════

def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

http = create_session()

# ═══════════════════════════════════════════════════════════
# DATA FETCHING
# ═══════════════════════════════════════════════════════════

def fetch_binance_ticker(pair: str) -> Optional[Dict]:
    print(f"  [FETCH BINANCE DATA] pair={pair}")
    url = f"https://fapi.binance.com/fapi/v1/ticker/24hr?symbol={pair}"
    try:
        r = http.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        price = data.get("lastPrice", "N/A")
        chg = data.get("priceChangePercent", "N/A")
        vol = data.get("quoteVolume", "N/A")
        log_info(f"→ price={price} | 24h_change={chg}% | volume={vol}")
        return data
    except Exception as e:
        log_error(f"Binance ticker {pair}: {e}")
        return None

def fetch_binance_klines(pair: str, interval: str, limit: int = 50) -> Optional[List]:
    print(f"  [FETCH KLINE] pair={pair} tf={interval}")
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={pair}&interval={interval}&limit={limit}"
    try:
        r = http.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        log_info(f"→ got {len(data)} candles")
        return data
    except Exception as e:
        log_error(f"Kline {pair} {interval}: {e}")
        return None

def fetch_open_interest(pair: str) -> Optional[Dict]:
    print(f"  [FETCH OPEN INTEREST] pair={pair}")
    url = f"https://fapi.binance.com/fapi/v1/openInterest?symbol={pair}"
    try:
        r = http.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        oi = data.get("openInterest", "N/A")
        log_info(f"→ OI={oi}")
        return data
    except Exception as e:
        log_error(f"OI {pair}: {e}")
        return None

def fetch_fear_greed() -> Optional[int]:
    print("  [FETCH FEAR & GREED]")
    url = "https://api.alternative.me/fng/?limit=1"
    try:
        r = http.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        value = int(data["data"][0]["value"])
        classification = data["data"][0]["value_classification"]
        log_info(f"→ value={value} ({classification})")
        return value
    except Exception as e:
        log_error(f"Fear & Greed: {e}")
        return None

def fetch_dexscreener(pair: str) -> Optional[Dict]:
    print(f"  [FETCH DEXSCREENER] pair={pair}")
    base = pair.replace("USDT", "").replace("USDC", "")
    url = f"https://api.dexscreener.com/latest/dex/search?q={base}%20USDT"
    try:
        r = http.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        pairs = data.get("pairs", [])
        if pairs:
            p = pairs[0]
            liquidity = p.get("liquidity", {}).get("usd", 0)
            volume = p.get("volume", {}).get("h24", 0)
            log_info(f"→ liquidity=${liquidity} | volume=${volume}")
            return p
        else:
            log_info("→ no DEX pair found")
            return None
    except Exception as e:
        log_error(f"Dexscreener {pair}: {e}")
        return None

# ═══════════════════════════════════════════════════════════
# TRENDING FILTER — pilih TOP 5–10 PAIRS dari universe
# ═══════════════════════════════════════════════════════════

def rank_pairs_by_volume(universe_data: Dict[str, Dict]) -> List[str]:
    """Rank pair berdasarkan absolute 24h volume (quoteVolume)."""
    scored = []
    for pair, data in universe_data.items():
        try:
            vol = float(data.get("quoteVolume", 0))
        except (ValueError, TypeError):
            vol = 0
        scored.append((pair, vol))
    scored.sort(key=lambda x: x[1], reverse=True)
    # Ambil top 5-10
    top_pairs = [p[0] for p in scored[:TRENDING_COUNT_MAX]]
    # Minimum 5
    if len(top_pairs) < TRENDING_COUNT_MIN:
        top_pairs = [p[0] for p in scored[:TRENDING_COUNT_MIN]]
    print(f"\n  🔥 TRENDING FILTER: selected top {len(top_pairs)} pairs by volume")
    for i, p in enumerate(top_pairs, 1):
        print(f"     {i}. {p}")
    return top_pairs

# ═══════════════════════════════════════════════════════════
# LAYER 1: MARKET ENVIRONMENT
# ═══════════════════════════════════════════════════════════

def analyze_market_environment(fear_greed: Optional[int], btc_data: Optional[Dict]) -> str:
    log_header("MARKET ENVIRONMENT — Analyze BTC Context")
    if btc_data is None:
        log_warn("No BTC data → default NEUTRAL")
        return "NEUTRAL"

    try:
        btc_change = float(btc_data.get("priceChangePercent", 0))
        btc_vol = float(btc_data.get("quoteVolume", 0))
        btc_high = float(btc_data.get("highPrice", 0))
        btc_low = float(btc_data.get("lowPrice", 0))
    except (ValueError, TypeError):
        log_warn("Invalid BTC data → NEUTRAL")
        return "NEUTRAL"

    # Volatility: range persentase
    volatility = ((btc_high - btc_low) / btc_low * 100) if btc_low > 0 else 0
    fg = fear_greed if fear_greed is not None else 50

    log_info(f"→ trend={'UP' if btc_change > 0 else 'DOWN' if btc_change < 0 else 'FLAT'} ({btc_change:.2f}%)")
    log_info(f"→ volatility={volatility:.2f}%")
    log_info(f"→ Fear&Greed={fg}")

    # Decision
    if fg > 60 and btc_change > 1 and volatility < 5:
        result = "HEALTHY"
    elif fg < 40 and btc_change < -1 and volatility > 5:
        result = "RISKY"
    else:
        result = "NEUTRAL"

    log_result(f"MARKET ENVIRONMENT = {result}")
    return result

# ═══════════════════════════════════════════════════════════
# LAYER 2: PAIR ANALYSIS (multi-timeframe)
# ═══════════════════════════════════════════════════════════

def analyze_pair(klines_dict: Dict[str, Optional[List]]) -> Tuple[str, str]:
    log_header("PAIR ANALYSIS — Multi-Timeframe")
    trends = []
    momentums = []

    for tf in TIMEFRAMES:
        klines = klines_dict.get(tf)
        if klines is None or len(klines) < 20:
            log_info(f"[ANALYZE PAIR TF {tf}] → SKIP (insufficient data)")
            continue

        closes = [float(k[4]) for k in klines]
        sma7 = sum(closes[-7:]) / min(7, len(closes[-7:]))
        sma20 = sum(closes[-20:]) / min(20, len(closes[-20:]))

        if sma7 > sma20:
            tf_trend = "BULLISH"
        elif sma7 < sma20:
            tf_trend = "BEARISH"
        else:
            tf_trend = "SIDEWAYS"

        # Momentum 5 candle
        if len(closes) >= 5:
            mom = ((closes[-1] - closes[-5]) / closes[-5]) * 100
            if mom > 0.5:
                tf_mom = "STRONG"
            elif mom < -0.5:
                tf_mom = "WEAK"
            else:
                tf_mom = "NEUTRAL"
        else:
            tf_mom = "NEUTRAL"

        log_info(f"[ANALYZE PAIR TF {tf}] → trend={tf_trend} | momentum={tf_mom} (mom={mom:.2f}%)")
        trends.append(tf_trend)
        momentums.append(tf_mom)

    # Majority vote
    def majority(votes):
        b = votes.count("BULLISH") if "BULLISH" in votes else votes.count("UP")
        be = votes.count("BEARISH") if "BEARISH" in votes else votes.count("DOWN")
        if b > be:
            return "BULLISH"
        elif be > b:
            return "BEARISH"
        return "SIDEWAYS"

    trend_final = majority(trends)
    mom_final = "STRONG" if momentums.count("STRONG") > momentums.count("WEAK") else (
        "WEAK" if momentums.count("WEAK") > momentums.count("STRONG") else "NEUTRAL"
    )

    log_result(f"PAIR ANALYSIS → trend={trend_final} | momentum={mom_final}")
    return trend_final, mom_final

# ═══════════════════════════════════════════════════════════
# LAYER 3: DERIVATIVES CONTEXT
# ═══════════════════════════════════════════════════════════

def analyze_derivatives(oi_data: Optional[Dict], ticker: Optional[Dict], trend: str) -> str:
    log_header("DERIVATIVES CONTEXT — Open Interest Analysis")
    if oi_data is None or ticker is None:
        log_warn("No OI/ticker data → NEUTRAL")
        return "NEUTRAL"

    try:
        oi = float(oi_data.get("openInterest", 0))
        price = float(ticker.get("lastPrice", 0))
        chg = float(ticker.get("priceChangePercent", 0))
    except (ValueError, TypeError):
        log_warn("Invalid OI/ticker → NEUTRAL")
        return "NEUTRAL"

    log_info(f"→ OI={oi:.0f}")
    log_info(f"→ price_change={chg:.2f}%")
    log_info(f"→ pair_trend={trend}")

    # Logic
    if chg > 0.5 and trend == "BULLISH":
        result = "BULLISH POSITION"
    elif chg < -0.5 and trend == "BEARISH":
        result = "BEARISH POSITION"
    else:
        result = "NEUTRAL"

    log_result(f"DERIVATIVES = {result}")
    return result

# ═══════════════════════════════════════════════════════════
# LAYER 4: MARKET FLOW
# ═══════════════════════════════════════════════════════════

def analyze_flow(ticker: Optional[Dict], dex_data: Optional[Dict]) -> str:
    log_header("MARKET FLOW — Accumulation / Distribution")
    if ticker is None:
        log_warn("No ticker → NETRAL")
        return "NETRAL"

    try:
        chg = float(ticker.get("priceChangePercent", 0))
        vol = float(ticker.get("quoteVolume", 0))
    except (ValueError, TypeError):
        log_warn("Invalid ticker → NETRAL")
        return "NETRAL"

    dex_vol = 0
    if dex_data:
        try:
            dex_vol = float(dex_data.get("volume", {}).get("h24", 0))
        except (ValueError, TypeError, AttributeError):
            pass

    log_info(f"→ price_change={chg:.2f}%")
    log_info(f"→ binance_volume={vol:.0f}")
    log_info(f"→ dex_volume={dex_vol:.0f}")

    if chg > 0 and vol > 0:
        result = "AKUMULASI"
    elif chg < 0 and vol > 0:
        result = "DISTRIBUSI"
    else:
        result = "NETRAL"

    log_result(f"MARKET FLOW = {result}")
    return result

# ═══════════════════════════════════════════════════════════
# SQUEEZE RISK
# ═══════════════════════════════════════════════════════════

def calculate_squeeze_risk(oi_data: Optional[Dict], ticker: Optional[Dict], trend: str) -> str:
    log_header("SQUEEZE RISK")
    if oi_data is None or ticker is None:
        log_info("→ default: LOW")
        return "LOW"

    try:
        oi = float(oi_data.get("openInterest", 0))
        chg = float(ticker.get("priceChangePercent", 0))
        vol = float(ticker.get("quoteVolume", 0))
    except (ValueError, TypeError):
        return "LOW"

    log_info(f"→ OI={oi:.0f} | change={chg:.2f}% | volume={vol:.0f}")

    # Rules
    if abs(chg) < 0.3 and oi > 0:
        result = "MEDIUM"
        log_info("→ OI↑ + price sideways → MEDIUM")
    elif (chg > 0 and trend == "BEARISH") or (chg < 0 and trend == "BULLISH"):
        result = "HIGH"
        log_info("→ OI↑ + price opposite direction → HIGH")
    elif vol > 0 and abs(chg) > 2:
        result = "HIGH"
        log_info("→ volume spike mismatch → HIGH")
    else:
        result = "LOW"
        log_info("→ normal conditions → LOW")

    log_result(f"SQUEEZE RISK = {result}")
    return result

# ═══════════════════════════════════════════════════════════
# LAYER 5: DECISION ENGINE
# ═══════════════════════════════════════════════════════════

def decision_engine(env: str, trend: str, momentum: str, derivatives: str, flow: str) -> str:
    log_header("DECISION ENGINE — Final Signal")

    bullish_score = 0
    bearish_score = 0

    log_info("condition_check:")
    log_info(f"  - env={env}")
    if env == "HEALTHY":
        bullish_score += 1
        log_info("    → HEALTHY supports BULLISH (+1)")
    elif env == "RISKY":
        bearish_score += 1
        log_info("    → RISKY supports BEARISH (+1)")

    log_info(f"  - trend={trend}")
    if trend == "BULLISH":
        bullish_score += 1
        log_info("    → BULLISH trend (+1)")
    elif trend == "BEARISH":
        bearish_score += 1
        log_info("    → BEARISH trend (+1)")

    log_info(f"  - momentum={momentum}")
    if momentum == "STRONG":
        bullish_score += 1
        log_info("    → STRONG momentum (+1)")
    elif momentum == "WEAK":
        bearish_score += 1
        log_info("    → WEAK momentum (+1)")

    log_info(f"  - flow={flow}")
    if flow == "AKUMULASI":
        bullish_score += 1
        log_info("    → AKUMULASI supports BULLISH (+1)")
    elif flow == "DISTRIBUSI":
        bearish_score += 1
        log_info("    → DISTRIBUSI supports BEARISH (+1)")

    log_info(f"  - derivatives={derivatives}")
    if "BULLISH" in derivatives:
        bullish_score += 1
        log_info("    → BULLISH derivatives (+1)")
    elif "BEARISH" in derivatives:
        bearish_score += 1
        log_info("    → BEARISH derivatives (+1)")

    # Decision
    log_info(f"\n  SCORE: bullish={bullish_score} | bearish={bearish_score}")

    if bullish_score >= 4:
        result = "LONG"
    elif bearish_score >= 4:
        result = "SHORT"
    else:
        result = "NO TRADE"

    log_result(f"DECISION = {result}")
    return result

# ═══════════════════════════════════════════════════════════
# ENTRY, SL, TP
# ═══════════════════════════════════════════════════════════

def calc_levels(ticker: Optional[Dict], signal: str) -> Tuple[float, float, float]:
    if ticker is None:
        return 0, 0, 0
    try:
        price = float(ticker.get("lastPrice", 0))
    except (ValueError, TypeError):
        return 0, 0, 0

    if price <= 0:
        return 0, 0, 0

    if signal == "LONG":
        entry = price
        sl = entry * (1 - SL_PERCENT / 100)
        tp = entry * (1 + TP_PERCENT / 100)
    elif signal == "SHORT":
        entry = price
        sl = entry * (1 + SL_PERCENT / 100)
        tp = entry * (1 - TP_PERCENT / 100)
    else:
        return price, 0, 0

    return round(entry, 4), round(sl, 4), round(tp, 4)

# ═══════════════════════════════════════════════════════════
# TELEGRAM SENDER
# ═══════════════════════════════════════════════════════════

def send_telegram(pair: str, signal_data: Dict) -> None:
    log_header(f"SEND TELEGRAM — {pair}")
    if TELEGRAM_BOT_TOKEN == "ISI_TOKEN_BOT_DISINI":
        log_warn("Telegram not configured → SKIP")
        return

    signal = signal_data["result"]
    entry = signal_data.get("entry", 0)
    sl = signal_data.get("sl", 0)
    tp = signal_data.get("tp", 0)
    flow = signal_data.get("market_flow", "NETRAL")
    squeeze = signal_data.get("squeeze_risk", "LOW")
    emoji = {"LONG": "🟢", "SHORT": "🔴", "NO TRADE": "⚪"}.get(signal, "⚪")

    message = f"""{emoji} {pair} | SYSTEM3 SIGNAL

🎯 SIGNAL: {signal}

💰 ENTRY: {entry}
🛑 SL: {sl}
🎯 TP: {tp}
⚖️ RR: {RR_RATIO}

💡 DSS INSIGHT:
📊 MARKET FLOW: {flow}
⚡ SQUEEZE RISK: {squeeze}
📌 ACTION GUIDE:

⚠️ DISCLAIMER:
Sinyal ini adalah Decision Support System.
Bukan rekomendasi finansial.
Gunakan manajemen risiko Anda sendiri.
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = http.post(url, json=payload, timeout=15)
        if r.status_code == 200:
            log_result(f"[SEND TELEGRAM] pair={pair} signal={signal} → SUCCESS")
        else:
            log_error(f"Telegram send failed: {r.status_code} {r.text}")
    except Exception as e:
        log_error(f"Telegram error: {e}")

# ═══════════════════════════════════════════════════════════
# GITHUB STORAGE (APPEND ONLY)
# ═══════════════════════════════════════════════════════════

def save_signal(signal_data: Dict) -> None:
    log_header("SAVE SIGNAL")
    base_dir = Path.home() / GITHUB_PATH
    base_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"signals_{date_str}.json"
    filepath = base_dir / filename

    existing = []
    if filepath.exists():
        try:
            with open(filepath, "r") as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            existing = []

    existing.append(signal_data)

    with open(filepath, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    log_result(f"Saved locally: {filepath}")
    push_github(filepath)

def push_github(filepath: Path) -> None:
    if GITHUB_TOKEN == "ISI_GITHUB_TOKEN_DISINI":
        log_info("[SAVE TO GITHUB] GitHub not configured → SKIP")
        return

    filename = filepath.name
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}/{filename}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

    with open(filepath, "r") as f:
        content = f.read()
    encoded = base64.b64encode(content.encode()).decode()

    try:
        r = http.get(url, headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None

        payload = {"message": f"Update {filename}", "content": encoded, "branch": GITHUB_BRANCH}
        if sha:
            payload["sha"] = sha

        r = http.put(url, headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            log_result("[SAVE TO GITHUB] status=SUCCESS")
        else:
            log_error(f"[SAVE TO GITHUB] status=FAIL ({r.status_code})")
    except Exception as e:
        log_error(f"[SAVE TO GITHUB] error: {e}")

# ═══════════════════════════════════════════════════════════
# MAIN CYCLE
# ═══════════════════════════════════════════════════════════

def run_cycle() -> None:
    print("\n" + "█" * 55)
    print("  SYSTEM3 SIGNAL ENGINE — CYCLE START")
    print("█" * 55)
    log_timestamp()

    # Step 1: Fetch BTC + Fear & Greed
    btc = fetch_binance_ticker("BTCUSDT")
    fg = fetch_fear_greed()

    # Step 2: Fetch tickers for all universe pairs
    universe_data = {}
    for pair in PAIR_UNIVERSE:
        # SOLUSI 3: FILTER SEBELUM ANALISIS (anti error 400)
        if not is_valid_symbol(pair):
            normalized = normalize_symbol(pair)
            if normalized:
                print(f"  🔄 SYMBOL NORMALIZED: {pair} → {normalized}")
                pair = normalized
            else:
                print(f"  ⚠️  SKIP INVALID FUTURES: {pair}")
                continue

        data = fetch_binance_ticker(pair)
        if data:
            universe_data[pair] = data
        time.sleep(0.5)

    # Step 3: Trending filter
    top_pairs = rank_pairs_by_volume(universe_data)

    # Step 4: Analyze only top pairs
    for pair in top_pairs:
        print(f"\n{'─'*55}")
        print(f"  📊 ANALYZING: {pair}")
        print(f"{'─'*55}")

        # SOLUSI 3: Validasi ulang sebelum analisis lanjutan
        if not is_valid_symbol(pair):
            normalized = normalize_symbol(pair)
            if normalized:
                print(f"  🔄 SYMBOL NORMALIZED: {pair} → {normalized}")
                pair = normalized
            else:
                print(f"  ⚠️  SKIP INVALID FUTURES: {pair}")
                continue

        ticker = universe_data.get(pair)
        if not ticker:
            log_warn(f"No ticker data for {pair} → SKIP")
            continue

        # Fetch additional data
        oi = fetch_open_interest(pair)
        dex = fetch_dexscreener(pair)
        klines = {}
        for tf in TIMEFRAMES:
            klines[tf] = fetch_binance_klines(pair, tf)
            time.sleep(0.3)

        # LAYER 1: Market Environment
        env = analyze_market_environment(fg, btc)

        # LAYER 2: Pair Analysis
        trend, momentum = analyze_pair(klines)

        # LAYER 3: Derivatives
        derivatives = analyze_derivatives(oi, ticker, trend)

        # LAYER 4: Market Flow
        flow = analyze_flow(ticker, dex)

        # SQUEEZE RISK
        squeeze = calculate_squeeze_risk(oi, ticker, trend)

        # LAYER 5: Decision Engine
        signal = decision_engine(env, trend, momentum, derivatives, flow)

        # Entry, SL, TP
        entry, sl, tp = calc_levels(ticker, signal)

        # Build result
        result_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pair": pair,
            "signal": signal,
            "market_environment": env,
            "pair_analysis": {"trend": trend, "momentum": momentum, "timeframes": TIMEFRAMES},
            "derivatives": derivatives,
            "market_flow": flow,
            "squeeze_risk": squeeze,
            "result": signal,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "rr": RR_RATIO
        }

        # Save & Send
        save_signal(result_data)
        send_telegram(pair, result_data)

        time.sleep(1)

    # Summary
    log_header("CYCLE COMPLETE")
    log_info(f"[WAIT TIMER: {SLEEP_SECONDS}s]")
    print(f"\n{'█'*55}")
    print("  SLEEPING — Next cycle in 45 minutes")
    print(f"{'█'*55}\n")

# ═══════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════╗")
    print("║       SYSTEM3 SIGNAL ENGINE v2.0 PRODUCTION        ║")
    print("║       Termux Android | Full Transparency Mode      ║")
    print("║       Scheduler: 45 min | Risk: SL 3% TP 6%       ║")
    print("╚══════════════════════════════════════════════════════╝")

    if not FUTURES_SYMBOLS:
        print("❌ FATAL: Tidak bisa mengambil daftar simbol futures.")
        print("   Pastikan koneksi internet aktif dan Binance API bisa diakses.")
        sys.exit(1)

    cycle_num = 0
    while True:
        cycle_num += 1
        print(f"\n🔄 CYCLE #{cycle_num}")
        try:
            run_cycle()
        except KeyboardInterrupt:
            print("\n👋 SYSTEM3 stopped by user.")
            break
        except Exception as e:
            log_error(f"Fatal cycle error: {e}")
            print(f"\n💥 Error: {e}\nRestarting in 60s...\n")
            time.sleep(60)
            continue

        time.sleep(SLEEP_SECONDS)
