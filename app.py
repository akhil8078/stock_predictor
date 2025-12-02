# app.py
from flask import Flask, render_template, request
import os, time, random, traceback
import math
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ---------- Config ----------
CACHE_DIR = "data_cache"
STATIC_DIR = "static"
PLOT_FILE = "dashboard.png"
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

app = Flask(__name__)

# ---------- Cache / Fetch (robust) ----------
def _write_cache(symbol, df):
    path = os.path.join(CACHE_DIR, f"{symbol}.csv")
    try:
        df.to_csv(path)
    except Exception as e:
        print(f"[cache] write error for {symbol}: {e}")

def _read_cache(symbol):
    path = os.path.join(CACHE_DIR, f"{symbol}.csv")
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, index_col=0)
    except Exception:
        try:
            os.remove(path)
        except Exception:
            pass
        return None
    # safe index coercion
    try:
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df[~df.index.isna()]
    except Exception:
        pass
    if df.empty:
        return None
    return df

def fetch_stock_data(symbol: str, period="5y", cache_ttl_hours=24, max_retries=4):
    symbol = symbol.upper().strip()
    cache_path = os.path.join(CACHE_DIR, f"{symbol}.csv")
    # use fresh cache
    if os.path.exists(cache_path):
        age = (time.time() - os.path.getmtime(cache_path)) / 3600.0
        if age <= cache_ttl_hours:
            df_cached = _read_cache(symbol)
            if df_cached is not None:
                return df_cached

    attempt = 0
    last_exc = None
    while attempt < max_retries:
        attempt += 1
        try:
            df = yf.download(symbol, period=period, progress=False, threads=False)
            if df is None or df.empty:
                df = yf.Ticker(symbol).history(period=period)
            if df is None or df.empty:
                raise RuntimeError("yfinance returned empty DataFrame")
            try:
                df.index = pd.to_datetime(df.index, errors="coerce")
                df = df[~df.index.isna()]
            except Exception:
                pass
            if df.empty:
                raise RuntimeError("empty after index processing")
            _write_cache(symbol, df)
            return df
        except Exception as e:
            last_exc = e
            print(f"[fetch] attempt {attempt} error for {symbol}: {e}")
            traceback.print_exc()
            sleep_s = (2 ** attempt) + random.uniform(0, 1)
            if "rate" in str(e).lower() or "too many" in str(e).lower():
                sleep_s = max(sleep_s, 10 + random.random()*5)
            time.sleep(sleep_s)
    # fallback to stale cache
    df_cached = _read_cache(symbol)
    if df_cached is not None:
        return df_cached
    print("[fetch] all attempts failed:", last_exc)
    return None

# ---------- Technical Indicators ----------
def compute_indicators(df):
    """
    df must contain 'Close' and 'Volume' columns and datetime index.
    Returns dict of scalars (latest) and df with columns for plotting.
    """
    d = df.copy().sort_index()
    close = d['Close'].astype(float)

    # Moving averages
    d['MA20'] = close.rolling(window=20, min_periods=10).mean()
    d['MA50'] = close.rolling(window=50, min_periods=20).mean()
    d['MA200'] = close.rolling(window=200, min_periods=50).mean()

    # RSI (14)
    window = 14
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/window, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1/window, min_periods=window).mean()
    rs = avg_gain / (avg_loss.replace(0, np.nan))
    rsi = 100 - (100 / (1 + rs))
    d['RSI14'] = rsi

    # MACD (12,26,9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    d['MACD'] = macd
    d['MACD_SIGNAL'] = signal
    d['MACD_HIST'] = d['MACD'] - d['MACD_SIGNAL']

    # Latest values
    latest = {}
    latest['last_close'] = float(close.iloc[-1])
    latest['ma20'] = float(d['MA20'].iloc[-1]) if not pd.isna(d['MA20'].iloc[-1]) else None
    latest['ma50'] = float(d['MA50'].iloc[-1]) if not pd.isna(d['MA50'].iloc[-1]) else None
    latest['ma200'] = float(d['MA200'].iloc[-1]) if not pd.isna(d['MA200'].iloc[-1]) else None
    latest['rsi14'] = float(d['RSI14'].iloc[-1]) if not pd.isna(d['RSI14'].iloc[-1]) else None
    latest['macd'] = float(d['MACD'].iloc[-1]) if not pd.isna(d['MACD'].iloc[-1]) else None
    latest['macd_signal'] = float(d['MACD_SIGNAL'].iloc[-1]) if not pd.isna(d['MACD_SIGNAL'].iloc[-1]) else None
    latest['macd_hist'] = float(d['MACD_HIST'].iloc[-1]) if not pd.isna(d['MACD_HIST'].iloc[-1]) else None
    latest['volume'] = int(d['Volume'].iloc[-1]) if 'Volume' in d.columns else None

    return d, latest

# ---------- Plotting Dashboard (price + MAs, MACD, RSI) ----------
def save_dashboard_plot(symbol, df, out_path, years_to_show=6):
    d, latest = compute_indicators(df)
    s = d['Close'].copy().dropna()
    if s.empty:
        raise ValueError("No close data to plot")

    # limit to recent years for readability
    if years_to_show is not None:
        last = s.index.max()
        start = last - pd.DateOffset(years=years_to_show)
        d = d.loc[d.index >= start]

    # drop duplicates and ensure datetime index
    d = d[~d.index.duplicated(keep='last')].sort_index()

    # Create multi-panel figure
    fig = plt.figure(figsize=(14, 8), dpi=120)
    gs = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.18)

    # PRICE + MAs
    ax0 = fig.add_subplot(gs[0, 0])
    ax0.set_facecolor("#0B0B0B")
    ax0.plot(d.index, d['Close'], label='Close', color='#00d442', linewidth=1.6)
    if 'MA20' in d.columns: ax0.plot(d.index, d['MA20'], label='MA20', color='#00ff99', linewidth=1.0)
    if 'MA50' in d.columns: ax0.plot(d.index, d['MA50'], label='MA50', color='#00a85a', linewidth=1.0)
    if 'MA200' in d.columns: ax0.plot(d.index, d['MA200'], label='MA200', color='#009944', linewidth=1.0)
    ax0.set_title(f"{symbol} — Price & Moving Averages", color='white')
    ax0.legend(loc='upper left', fontsize=9)
    ax0.tick_params(axis='x', labelrotation=25)
    ax0.grid(alpha=0.18, color='#444444')
    ax0.set_ylabel("Price")

    # MACD
    ax1 = fig.add_subplot(gs[1, 0], sharex=ax0)
    ax1.set_facecolor("#0B0B0B")
    ax1.bar(d.index, d['MACD_HIST'], color=['#00d442' if v>=0 else '#ff5c5c' for v in d['MACD_HIST']], width=2)
    ax1.plot(d.index, d['MACD'], label='MACD', color='#00ffbe', linewidth=1)
    ax1.plot(d.index, d['MACD_SIGNAL'], label='Signal', color='#ffcc00', linewidth=1)
    ax1.set_ylabel("MACD")
    ax1.grid(alpha=0.12, color='#444444')

    # RSI
    ax2 = fig.add_subplot(gs[2, 0], sharex=ax0)
    ax2.set_facecolor("#0B0B0B")
    ax2.plot(d.index, d['RSI14'], color='#11FF66', linewidth=1)
    ax2.axhline(70, color='#ff5c5c', linestyle='--', linewidth=0.7)
    ax2.axhline(30, color='#0088ff', linestyle='--', linewidth=0.7)
    ax2.set_ylabel("RSI(14)")
    ax2.set_ylim(0, 100)
    ax2.grid(alpha=0.12, color='#444444')

    # Date locator formatting
    span_days = (d.index.max() - d.index.min()).days if len(d.index)>1 else 365
    if span_days > 365 * 6:
        locator = mdates.YearLocator()
        fmt = mdates.DateFormatter("%Y")
    elif span_days > 365:
        locator = mdates.MonthLocator(interval=6)
        fmt = mdates.DateFormatter("%Y-%m")
    else:
        locator = mdates.MonthLocator(interval=1)
        fmt = mdates.DateFormatter("%Y-%m")

    ax2.xaxis.set_major_locator(locator)
    ax2.xaxis.set_major_formatter(fmt)
    for ax in (ax0, ax1, ax2):
        for label in ax.get_xticklabels():
            label.set_color("#ddd")
            label.set_fontsize(9)
    fig.autofmt_xdate(rotation=25)

    # Save figure
    plt.tight_layout()
    plt.savefig(out_path, facecolor='#0B0B0B', bbox_inches='tight')
    plt.close(fig)

# ---------- Company info helper ----------
def get_company_info(symbol):
    try:
        tk = yf.Ticker(symbol)
        info = tk.info
        # pick safe fields
        company = {
            'symbol': symbol,
            'name': info.get('longName') or info.get('shortName') or symbol,
            'sector': info.get('sector', '—'),
            'industry': info.get('industry', '—'),
            'country': info.get('country', '—'),
            'currency': info.get('currency', 'USD'),
            'marketCap': info.get('marketCap'),
            'website': info.get('website'),
            'summary': info.get('longBusinessSummary'),
            'logo_url': info.get('logo_url') or info.get('photo_url') or None
        }
        return company
    except Exception as e:
        print("Company info fetch error:", e)
        return {'symbol': symbol, 'name': symbol}

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    symbol = request.form.get('stock_symbol', '').strip().upper()
    if not symbol:
        return "Please enter a symbol", 400

    df = fetch_stock_data(symbol)
    if df is None:
        return f"Could not fetch data for {symbol}. Try again later or delete cache.", 500

    if 'Close' not in df.columns:
        return f"No Close price available for {symbol}.", 500

    # compute indicators and plot
    try:
        save_dashboard_plot(symbol, df, os.path.join(STATIC_DIR, PLOT_FILE), years_to_show=6)
    except Exception as e:
        print("Plot error:", e)
        traceback.print_exc()
        return "Plotting failed", 500

    _, latest = compute_indicators(df)
    comp = get_company_info(symbol)

    # format marketCap human readable
    mc = comp.get('marketCap')
    if mc:
        # thousands/millions/billions
        if mc >= 1_000_000_000:
            mc_text = f"${mc/1_000_000_000:.2f}B"
        elif mc >= 1_000_000:
            mc_text = f"${mc/1_000_000:.2f}M"
        else:
            mc_text = f"${mc:,}"
    else:
        mc_text = "—"

    # safety for None numeric fields
    def nice(v, precision=2):
        return ("{0:." + str(precision) + "f}").format(v) if (v is not None and not (isinstance(v, float) and math.isnan(v))) else "—"

    indicator_snapshot = {
        'last_close': nice(latest.get('last_close')),
        'ma20': nice(latest.get('ma20')),
        'ma50': nice(latest.get('ma50')),
        'ma200': nice(latest.get('ma200')),
        'rsi14': nice(latest.get('rsi14')),
        'macd': nice(latest.get('macd'), 4),
        'macd_signal': nice(latest.get('macd_signal'), 4),
        'macd_hist': nice(latest.get('macd_hist'), 4),
        'volume': f"{latest.get('volume'):,}" if latest.get('volume') else "—",
    }

    return render_template('result.html',
                           stock=symbol,
                           company=comp,
                           market_cap=mc_text,
                           indicators=indicator_snapshot,
                           plot_file=PLOT_FILE)

# ---------- Run ----------
if __name__ == '__main__':
    app.run(debug=True)
