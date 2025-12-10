"""
Precious Metals Trading Coach - Dashboard

Shows live Gold (XAU) and Silver (XAG) prices with comprehensive indicators:
- Price levels (spot, futures, ATH, 52-week range)
- Moving averages (SMA & EMA)
- Momentum (RSI, MACD, OBV, Volume)
- COT positioning data
- Macro drivers
- Term structure analysis
- AI-powered market analysis

Run with:
    streamlit run app.py
"""
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from alpha_vantage_fetcher import fetch_gold_price, fetch_silver_price
from indicators import compute_indicators
from cot_fetcher import get_cot_summary
from macro_fetcher import get_macro_dashboard
from term_structure import analyze_term_structure
from ai_summary import generate_ai_summary, get_quick_verdict

# === PAGE CONFIG ===
st.set_page_config(
    page_title="Precious Metals Coach",
    page_icon="🥇",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# === PASSWORD PROTECTION ===
def check_password():
    """Returns True if the user has entered correct credentials."""

    def password_entered():
        """Checks whether credentials are correct."""
        try:
            correct_user = st.secrets["credentials"]["username"]
            correct_pass = st.secrets["credentials"]["password"]
        except (KeyError, FileNotFoundError):
            # No secrets configured - allow access (for local dev)
            st.session_state["authenticated"] = True
            return

        if (st.session_state.get("username") == correct_user and
            st.session_state.get("password") == correct_pass):
            st.session_state["authenticated"] = True
            del st.session_state["password"]  # Don't store password
            del st.session_state["username"]
        else:
            st.session_state["authenticated"] = False

    # Check if secrets are configured
    try:
        _ = st.secrets["credentials"]["username"]
        secrets_configured = True
    except (KeyError, FileNotFoundError):
        secrets_configured = False

    # If no secrets configured, allow access (local development)
    if not secrets_configured:
        return True

    # First run or not authenticated
    if "authenticated" not in st.session_state:
        st.markdown("""
        <div style="display: flex; justify-content: center; align-items: center; min-height: 60vh;">
            <div style="background: linear-gradient(145deg, #1e2530 0%, #252d3a 100%);
                        border-radius: 16px; padding: 40px; border: 1px solid #333;
                        box-shadow: 0 4px 20px rgba(0,0,0,0.3); max-width: 400px; width: 100%;">
                <h2 style="color: #FFD700; text-align: center; margin-bottom: 8px;">🥇 Precious Metals Coach</h2>
                <p style="color: #888; text-align: center; margin-bottom: 24px;">Enter credentials to access the dashboard</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Login", on_click=password_entered, use_container_width=True, type="primary")
        return False

    # Incorrect password
    elif not st.session_state["authenticated"]:
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.markdown("""
            <h2 style="color: #FFD700; text-align: center;">🥇 Precious Metals Coach</h2>
            """, unsafe_allow_html=True)
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Login", on_click=password_entered, use_container_width=True, type="primary")
            st.error("Invalid username or password")
        return False

    # Correct password
    return True


# Gate the entire app behind authentication
if not check_password():
    st.stop()

# === CUSTOM CSS FOR PROFESSIONAL STYLING ===
st.markdown("""
<style>
    /* ===== FORCE DARK THEME EVERYWHERE ===== */
    :root {
        color-scheme: dark !important;
    }

    /* Main background - force dark on all devices */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
    .main, .block-container, [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0e1117 0%, #1a1f2e 100%) !important;
        color: #ffffff !important;
    }

    /* Force all text to be light colored */
    .stApp p, .stApp span, .stApp div, .stApp label, .stApp h1, .stApp h2,
    .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stMarkdown,
    [data-testid="stMarkdownContainer"], [data-testid="stText"] {
        color: #ffffff !important;
    }

    /* Fix Streamlit native elements */
    .stSelectbox label, .stTextInput label, .stNumberInput label,
    .stRadio label, .stCheckbox label, .stSlider label {
        color: #ffffff !important;
    }

    .stSelectbox [data-baseweb="select"],
    .stTextInput input, .stNumberInput input {
        background-color: #1e2530 !important;
        color: #ffffff !important;
        border-color: #444 !important;
    }

    /* Tabs styling - prominent metal selector */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #1e2530 !important;
        border-radius: 12px;
        padding: 8px !important;
        gap: 8px !important;
        justify-content: center !important;
        border: 2px solid #333 !important;
    }

    .stTabs [data-baseweb="tab"] {
        color: #aaa !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        padding: 12px 32px !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background-color: #2a3444 !important;
        color: #fff !important;
    }

    .stTabs [aria-selected="true"] {
        color: #000 !important;
        background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%) !important;
        box-shadow: 0 4px 15px rgba(255, 215, 0, 0.3) !important;
    }

    /* Tab highlight indicator */
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Metal selector header */
    .metal-selector-header {
        text-align: center;
        color: #b0b0b0 !important;
        font-size: 0.95rem;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 2px;
    }

    /* Expander styling */
    .streamlit-expanderHeader {
        background: #1e2530 !important;
        border-radius: 8px !important;
        color: #ffffff !important;
    }

    .streamlit-expanderContent {
        background: #1a1f2e !important;
        color: #ffffff !important;
    }

    details summary span {
        color: #ffffff !important;
    }

    /* Header styling */
    .main-header {
        background: linear-gradient(90deg, #FFD700 0%, #FFA500 50%, #FFD700 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        font-size: 3rem;
        font-weight: 800;
        text-align: center;
        margin-bottom: 0;
        letter-spacing: -1px;
    }

    .sub-header {
        text-align: center;
        color: #b0b0b0 !important;
        font-size: 1.1rem;
        margin-top: -10px;
        margin-bottom: 30px;
    }

    /* Card styling */
    .metric-card {
        background: linear-gradient(145deg, #1e2530 0%, #252d3a 100%) !important;
        border-radius: 16px;
        padding: 20px;
        border: 1px solid #444;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        margin-bottom: 16px;
    }

    .metric-card-gold {
        border-left: 4px solid #FFD700;
    }

    .metric-card-silver {
        border-left: 4px solid #C0C0C0;
    }

    /* Price display */
    .price-large {
        font-size: 2.5rem;
        font-weight: 700;
        color: #fff !important;
        margin: 0;
    }

    .price-gold {
        color: #FFD700 !important;
    }

    .price-silver {
        color: #C0C0C0 !important;
    }

    /* Section headers */
    .section-header {
        font-size: 1.4rem;
        font-weight: 600;
        color: #fff !important;
        margin-top: 24px;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 2px solid #444;
    }

    /* Signal badges */
    .signal-bullish {
        background: linear-gradient(135deg, #00c853 0%, #00e676 100%);
        color: #000 !important;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }

    .signal-bearish {
        background: linear-gradient(135deg, #ff1744 0%, #ff5252 100%);
        color: #fff !important;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }

    .signal-neutral {
        background: linear-gradient(135deg, #455a64 0%, #607d8b 100%);
        color: #fff !important;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }

    /* Data row styling */
    .data-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid #3a3a3a;
    }

    .data-label {
        color: #b0b0b0 !important;
        font-size: 0.9rem;
    }

    .data-value {
        color: #fff !important;
        font-weight: 500;
        font-size: 0.9rem;
    }

    /* Verdict box */
    .verdict-box {
        background: linear-gradient(145deg, #1a2332 0%, #1e2940 100%) !important;
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        border: 2px solid #444;
    }

    .verdict-bullish {
        border-color: #00c853 !important;
        box-shadow: 0 0 30px rgba(0,200,83,0.2);
    }

    .verdict-bearish {
        border-color: #ff1744 !important;
        box-shadow: 0 0 30px rgba(255,23,68,0.2);
    }

    .verdict-neutral {
        border-color: #ffc107 !important;
        box-shadow: 0 0 30px rgba(255,193,7,0.2);
    }

    .verdict-text {
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
    }

    .verdict-score {
        font-size: 1rem;
        color: #b0b0b0 !important;
        margin-top: 4px;
    }

    /* Macro indicator cards */
    .macro-card {
        background: #1e2530 !important;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        border: 1px solid #444;
    }

    .macro-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #fff !important;
    }

    .macro-label {
        font-size: 0.8rem;
        color: #b0b0b0 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Custom divider */
    .custom-divider {
        height: 2px;
        background: linear-gradient(90deg, transparent 0%, #444 50%, transparent 100%);
        margin: 40px 0;
    }

    /* Info box */
    .info-box {
        background: rgba(255,215,0,0.15) !important;
        border: 1px solid rgba(255,215,0,0.4);
        border-radius: 8px;
        padding: 12px 16px;
        margin: 8px 0;
        color: #fff !important;
    }

    /* Timestamp */
    .timestamp {
        text-align: center;
        color: #888 !important;
        font-size: 0.85rem;
        margin-top: 40px;
    }

    /* ===== MOBILE RESPONSIVE STYLES ===== */
    @media (max-width: 768px) {
        .main-header {
            font-size: 2rem !important;
        }

        .sub-header {
            font-size: 0.95rem !important;
        }

        .price-large {
            font-size: 1.8rem !important;
        }

        .metric-card {
            padding: 15px !important;
        }

        .verdict-text {
            font-size: 1.4rem !important;
        }

        .verdict-box {
            padding: 16px !important;
        }

        .macro-value {
            font-size: 1.2rem !important;
        }

        .section-header {
            font-size: 1.2rem !important;
        }

        /* Better touch targets on mobile */
        .stButton button {
            min-height: 48px !important;
            font-size: 1rem !important;
        }

        /* Improve readability on small screens */
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }

        /* More prominent tabs on mobile */
        .stTabs [data-baseweb="tab-list"] {
            flex-direction: column !important;
            padding: 12px !important;
        }

        .stTabs [data-baseweb="tab"] {
            width: 100% !important;
            padding: 16px 24px !important;
            font-size: 1.2rem !important;
            justify-content: center !important;
        }

        .metal-selector-header {
            font-size: 0.85rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# === HELPER FUNCTIONS ===
def format_price(value, prefix="$"):
    if value is None:
        return "N/A"
    return f"{prefix}{value:,.2f}"

def format_pct(value, show_sign=True):
    if value is None:
        return "N/A"
    if show_sign:
        return f"{value:+.2f}%"
    return f"{value:.1f}%"

def format_number(value, decimals=0):
    if value is None:
        return "N/A"
    if decimals == 0:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"

def get_signal_class(signal):
    if signal in ["bullish", "uptrend", "rising", "strong_buying", "buying", "strongly bullish", "mildly bullish"]:
        return "signal-bullish"
    elif signal in ["bearish", "downtrend", "falling", "strong_selling", "selling"]:
        return "signal-bearish"
    return "signal-neutral"

def signal_badge(text, signal_type):
    css_class = get_signal_class(signal_type)
    return f'<span class="{css_class}">{text}</span>'

def signal_emoji(signal):
    if signal in ["bullish", "uptrend", "rising", "strong_buying", "buying"]:
        return "🟢"
    elif signal in ["bearish", "downtrend", "falling", "strong_selling", "selling"]:
        return "🔴"
    elif signal in ["extreme_long", "extreme_short"]:
        return "🟡"
    return "⚪"

# === HEADER ===
st.markdown('<h1 class="main-header">Precious Metals Trading Coach</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Real-time analysis powered by institutional-grade indicators & AI</p>', unsafe_allow_html=True)

# === DATA FETCHING ===
with st.spinner(""):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        progress = st.progress(0, text="Loading market data...")

        progress.progress(10, text="Fetching spot prices...")
        gold_price, gold_raw = fetch_gold_price()
        silver_price, silver_raw = fetch_silver_price()

        progress.progress(30, text="Computing technical indicators...")
        gold_ind = compute_indicators("GC=F", spot_price=gold_price)
        silver_ind = compute_indicators("SI=F", spot_price=silver_price)

        progress.progress(50, text="Fetching COT positioning data...")
        try:
            gold_cot = get_cot_summary("GOLD")
            silver_cot = get_cot_summary("SILVER")
        except Exception as e:
            gold_cot = {"error": str(e)}
            silver_cot = {"error": str(e)}

        progress.progress(70, text="Loading macro indicators...")
        try:
            macro_data = get_macro_dashboard()
        except Exception as e:
            macro_data = {"error": str(e), "indicators": {}}

        progress.progress(90, text="Analyzing term structure...")
        try:
            gold_term = analyze_term_structure("gold", spot_price=gold_price)
            silver_term = analyze_term_structure("silver", spot_price=silver_price)
        except Exception as e:
            gold_term = {"error": str(e)}
            silver_term = {"error": str(e)}

        progress.progress(100, text="Complete!")
        progress.empty()

# === EDUCATIONAL CONTENT ===
PRICE_LEVELS_GUIDE = """
**Why it matters:** Price levels show where the market is relative to historical extremes.

**Buy signals:**
- Price near 52-week low with bullish divergence
- Breakout above previous ATH (new highs = strong momentum)
- Price >10% below ATH in a secular bull market = potential value

**Sell signals:**
- Price at ATH with overbought RSI (>70)
- Failed breakout above resistance
- Price >50% above 200-day MA (overextended)
"""

TREND_MA_GUIDE = """
**Why it matters:** Moving averages smooth price action and reveal the underlying trend. The 200-day MA is watched by institutions worldwide.

**Buy signals:**
- Price crosses above 200-day MA ("Golden Cross" setup)
- 50-day MA crosses above 200-day MA (confirmed Golden Cross)
- Price > 20 > 50 > 200 MA alignment = strong uptrend
- Pullback to rising 50-day MA = buy the dip

**Sell signals:**
- Price crosses below 200-day MA
- 50-day MA crosses below 200-day MA ("Death Cross")
- Price < 20 < 50 < 200 MA alignment = strong downtrend
- "Chop" regime = stay flat, wait for clarity
"""

MOMENTUM_GUIDE = """
**Why it matters:** Momentum indicators show the *strength* behind price moves.

**RSI signals:**
- RSI < 30 = oversold (BUY) | RSI > 70 = overbought (SELL)

**MACD signals:**
- MACD crosses above signal = BUY | Below = SELL
- Histogram rising = momentum building

**OBV signals:**
- OBV rising + price rising = confirmed uptrend
- OBV falling + price rising = divergence warning
"""

COT_GUIDE = """
**Why it matters:** COT shows what the "smart money" (commercials) and "trend followers" (managed money) are doing.

**Commercial Hedgers:** Always net short. LESS short (high %) = BULLISH, MORE short (low %) = BEARISH

**Managed Money:** Extreme long (>80%) = crowded SELL, Extreme short (<20%) = contrarian BUY
"""

MACRO_GUIDE = """
**Real Yields (10Y TIPS) - THE #1 DRIVER:** Negative = BULLISH, Rising = BEARISH

**US Dollar (DXY):** Inverse correlation. DXY falling = BULLISH for gold

**VIX:** > 25 = risk-off BULLISH | MOVE > 100 = bond stress BULLISH
"""

TERM_STRUCTURE_GUIDE = """
**Contango (Futures > Spot):** Normal due to carry costs. Steep (>3%) = BEARISH

**Backwardation (Spot > Futures):** RARE and strongly BULLISH - indicates physical shortage
"""

# === HERO SECTION - LIVE PRICES ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

hero_col1, hero_col2 = st.columns(2)

with hero_col1:
    if gold_price:
        pct_from_high = gold_ind.get('pct_from_52w_high', 0) if "error" not in gold_ind else 0
        trend = gold_ind.get('trend', 'unknown') if "error" not in gold_ind else 'unknown'

        st.markdown(f"""
        <div class="metric-card metric-card-gold">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #888; font-size: 0.9rem;">GOLD (XAU/USD)</span>
                    <h2 class="price-large price-gold">{format_price(gold_price)}</h2>
                    <span style="color: {'#00c853' if pct_from_high >= 0 else '#ff5252'}; font-size: 0.95rem;">
                        {pct_from_high:+.2f}% from 52w high
                    </span>
                </div>
                <div style="text-align: right;">
                    {signal_badge(trend.upper(), trend)}
                    <p style="color: #666; font-size: 0.8rem; margin-top: 8px;">Source: Gold-API</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("Gold price unavailable")

with hero_col2:
    if silver_price:
        pct_from_high = silver_ind.get('pct_from_52w_high', 0) if "error" not in silver_ind else 0
        trend = silver_ind.get('trend', 'unknown') if "error" not in silver_ind else 'unknown'

        st.markdown(f"""
        <div class="metric-card metric-card-silver">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #888; font-size: 0.9rem;">SILVER (XAG/USD)</span>
                    <h2 class="price-large price-silver">{format_price(silver_price)}</h2>
                    <span style="color: {'#00c853' if pct_from_high >= 0 else '#ff5252'}; font-size: 0.95rem;">
                        {pct_from_high:+.2f}% from 52w high
                    </span>
                </div>
                <div style="text-align: right;">
                    {signal_badge(trend.upper(), trend)}
                    <p style="color: #666; font-size: 0.8rem; margin-top: 8px;">Source: Gold-API</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("Silver price unavailable")

# === AI VERDICT SECTION ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown("### 🤖 AI Market Verdict")

verdict_col1, verdict_col2 = st.columns(2)

with verdict_col1:
    if "error" not in gold_ind:
        gold_verdict = get_quick_verdict(gold_ind, gold_cot, macro_data, gold_term)
        verdict = gold_verdict["verdict"]
        score = gold_verdict["net_score"]

        if "BULLISH" in verdict:
            verdict_class = "verdict-bullish"
            verdict_color = "#00c853"
        elif "BEARISH" in verdict:
            verdict_class = "verdict-bearish"
            verdict_color = "#ff1744"
        else:
            verdict_class = "verdict-neutral"
            verdict_color = "#ffc107"

        st.markdown(f"""
        <div class="verdict-box {verdict_class}">
            <p style="color: #888; font-size: 0.9rem; margin: 0;">GOLD</p>
            <p class="verdict-text" style="color: {verdict_color};">{verdict}</p>
            <p class="verdict-score">Score: {score:+d} | Bullish: {gold_verdict['bullish_signals']} | Bearish: {gold_verdict['bearish_signals']}</p>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("View Signal Breakdown"):
            for name, direction, desc in gold_verdict['signals']:
                emoji = signal_emoji(direction)
                st.write(f"{emoji} **{name}:** {desc}")

with verdict_col2:
    if "error" not in silver_ind:
        silver_verdict = get_quick_verdict(silver_ind, silver_cot, macro_data, silver_term)
        verdict = silver_verdict["verdict"]
        score = silver_verdict["net_score"]

        if "BULLISH" in verdict:
            verdict_class = "verdict-bullish"
            verdict_color = "#00c853"
        elif "BEARISH" in verdict:
            verdict_class = "verdict-bearish"
            verdict_color = "#ff1744"
        else:
            verdict_class = "verdict-neutral"
            verdict_color = "#ffc107"

        st.markdown(f"""
        <div class="verdict-box {verdict_class}">
            <p style="color: #888; font-size: 0.9rem; margin: 0;">SILVER</p>
            <p class="verdict-text" style="color: {verdict_color};">{verdict}</p>
            <p class="verdict-score">Score: {score:+d} | Bullish: {silver_verdict['bullish_signals']} | Bearish: {silver_verdict['bearish_signals']}</p>
        </div>
        """, unsafe_allow_html=True)

        with st.expander("View Signal Breakdown"):
            for name, direction, desc in silver_verdict['signals']:
                emoji = signal_emoji(direction)
                st.write(f"{emoji} **{name}:** {desc}")

# === MACRO DRIVERS ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown("### 🌍 Macro Environment")

with st.expander("ℹ️ Understanding Macro Drivers", expanded=False):
    st.markdown(MACRO_GUIDE)

if "error" not in macro_data:
    macro_bias = macro_data.get("macro_bias", "neutral")
    indicators = macro_data.get("indicators", {})

    # Overall bias banner
    if macro_bias == "bullish":
        st.success(f"**Overall Macro Bias:** 🟢 BULLISH FOR GOLD")
    elif macro_bias == "bearish":
        st.error(f"**Overall Macro Bias:** 🔴 BEARISH FOR GOLD")
    else:
        st.warning(f"**Overall Macro Bias:** ⚪ NEUTRAL")

    m1, m2, m3, m4, m5 = st.columns(5)

    with m1:
        dxy = indicators.get("dxy", {})
        if "error" not in dxy:
            val = dxy.get("value", 0)
            chg = dxy.get("change", 0)
            impact = dxy.get("gold_impact", "neutral")
            st.metric("DXY (Dollar)", f"{val:.2f}", f"{chg:+.2f}", delta_color="inverse")
            st.caption(f"Gold: {signal_emoji(impact)} {impact}")

    with m2:
        us10y = indicators.get("us10y", {})
        if "error" not in us10y:
            val = us10y.get("value", 0)
            chg = us10y.get("change", 0)
            st.metric("10Y Yield", f"{val:.2f}%", f"{chg:+.2f}%", delta_color="inverse")

    with m3:
        real = indicators.get("real_yield", {})
        if "current" in real:
            val = real.get("current", 0)
            chg = real.get("change")
            impact = real.get("gold_impact", "neutral")
            delta_str = f"{chg:+.2f}%" if chg else None
            st.metric("10Y Real Yield", f"{val:.2f}%", delta_str, delta_color="inverse")
            st.caption(f"Gold: {signal_emoji(impact)} {impact}")

    with m4:
        vix = indicators.get("vix", {})
        if "error" not in vix:
            val = vix.get("value", 0)
            chg = vix.get("change", 0)
            regime = vix.get("regime", "")
            st.metric("VIX", f"{val:.1f}", f"{chg:+.1f}")
            st.caption(regime)

    with m5:
        move = indicators.get("move", {})
        if "error" not in move:
            val = move.get("value", 0)
            chg = move.get("change", 0)
            regime = move.get("regime", "")
            st.metric("MOVE Index", f"{val:.1f}", f"{chg:+.1f}")
            st.caption(regime)

# === TECHNICAL ANALYSIS TABS ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown("### 📊 Technical Analysis")
st.markdown('<p class="metal-selector-header">👇 Select a metal to view detailed analysis</p>', unsafe_allow_html=True)

tab_gold, tab_silver = st.tabs(["🥇 GOLD", "🥈 SILVER"])

def render_technical_tab(ind, cot, term, metal_name):
    """Render technical analysis for a metal."""
    if "error" in ind:
        st.error(f"Technical data unavailable: {ind.get('error')}")
        return

    # Price Levels & Moving Averages
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 📍 Price Levels")
        with st.expander("ℹ️ What to look for"):
            st.markdown(PRICE_LEVELS_GUIDE)

        st.markdown(f"""
        | Level | Price |
        |-------|-------|
        | **Spot** | {format_price(ind.get('spot_price') or ind.get('last_close'))} |
        | **Futures** | {format_price(ind.get('futures_price'))} |
        | **All-Time High** | {format_price(ind.get('ath'))} |
        | **52w High** | {format_price(ind.get('52w_high'))} |
        | **52w Low** | {format_price(ind.get('52w_low'))} |
        | **% from ATH** | {format_pct(ind.get('pct_from_ath'))} |
        """)

    with col2:
        st.markdown("#### 📈 Moving Averages")
        with st.expander("ℹ️ What to look for"):
            st.markdown(TREND_MA_GUIDE)

        trend = ind.get('trend', 'unknown')
        st.markdown(f"**Trend:** {signal_badge(trend.upper(), trend)}", unsafe_allow_html=True)

        ma_col1, ma_col2 = st.columns(2)
        with ma_col1:
            st.markdown(f"""
            **SMA**
            - 20: {format_price(ind.get('sma20'))}
            - 50: {format_price(ind.get('sma50'))}
            - 200: {format_price(ind.get('sma200'))}
            """)
        with ma_col2:
            st.markdown(f"""
            **EMA**
            - 20: {format_price(ind.get('ema20'))}
            - 50: {format_price(ind.get('ema50'))}
            - 200: {format_price(ind.get('ema200'))}
            """)

    # Momentum & COT
    col3, col4 = st.columns(2)

    with col3:
        st.markdown("#### ⚡ Momentum")
        with st.expander("ℹ️ What to look for"):
            st.markdown(MOMENTUM_GUIDE)

        rsi = ind.get('rsi14')
        rsi_signal = "overbought" if rsi and rsi > 70 else "oversold" if rsi and rsi < 30 else "neutral"
        macd_cross = ind.get('macd_crossover', 'unknown')
        macd_slope = ind.get('macd_histogram_slope', 'unknown')
        obv_trend = ind.get('obv_trend', 'unknown')
        vol_ratio = ind.get('volume_ratio')
        vol_signal = ind.get('volume_signal', 'N/A')

        st.markdown(f"""
        | Indicator | Value | Signal |
        |-----------|-------|--------|
        | **RSI(14)** | {format_number(rsi, 1)} | {signal_emoji(rsi_signal)} {rsi_signal} |
        | **MACD** | {macd_cross} | {signal_emoji(macd_cross)} histogram {macd_slope} |
        | **OBV** | - | {signal_emoji(obv_trend)} {obv_trend} |
        | **Volume** | {format_number(vol_ratio, 2) if vol_ratio else 'N/A'}x avg | {vol_signal} |
        """)

    with col4:
        st.markdown("#### 🏦 COT Positioning")
        with st.expander("ℹ️ What to look for"):
            st.markdown(COT_GUIDE)

        if "error" not in cot:
            comm_signal = cot.get('commercial_signal', 'neutral')
            mm_signal = cot.get('managed_money_signal', 'neutral')
            mm_momentum = cot.get('mm_momentum', 'unknown')

            st.caption(f"Report: {cot.get('report_date', 'N/A')}")

            st.markdown(f"""
            **Commercial Hedgers** {signal_emoji(comm_signal)}
            - Net: {format_number(cot.get('commercial_net'))}
            - Percentile: {format_pct(cot.get('commercial_percentile'), False)}

            **Managed Money** {signal_emoji(mm_signal)} ({mm_momentum})
            - Net: {format_number(cot.get('managed_money_net'))}
            - Percentile: {format_pct(cot.get('managed_money_percentile'), False)}

            **Open Interest:** {format_number(cot.get('open_interest'))}
            """)
        else:
            st.warning("COT data unavailable")

    # Term Structure
    st.markdown("#### 📐 Term Structure")
    with st.expander("ℹ️ What to look for"):
        st.markdown(TERM_STRUCTURE_GUIDE)

    if "error" not in term:
        structure = term.get("structure", "unknown")
        signal = term.get("signal", "neutral")
        spread_pct = term.get("spread_pct", 0)
        ann_basis = term.get("annualized_basis_pct", 0)

        ts1, ts2, ts3 = st.columns(3)
        with ts1:
            st.metric("Structure", structure.upper())
        with ts2:
            st.metric("Spread", f"{spread_pct:+.2f}%")
        with ts3:
            st.metric("Ann. Basis", f"{ann_basis:+.1f}%")

        st.markdown(f"**Signal:** {signal_badge(signal, signal)} - {term.get('interpretation', '')}", unsafe_allow_html=True)

    # Price Chart
    st.markdown("#### 📉 Price Chart (180 Days)")
    hist = ind.get("history")
    if hist is not None and not hist.empty:
        st.line_chart(hist['Close'].tail(180), use_container_width=True)

with tab_gold:
    render_technical_tab(gold_ind, gold_cot, gold_term, "Gold")

with tab_silver:
    render_technical_tab(silver_ind, silver_cot, silver_term, "Silver")

# === DETAILED AI ANALYSIS ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown("### 🧠 Detailed AI Analysis")
st.caption("Click to generate a comprehensive AI-powered market analysis")

ai_col1, ai_col2 = st.columns(2)

with ai_col1:
    if st.button("🥇 Generate Gold Analysis", use_container_width=True, type="primary"):
        with st.spinner("Claude is analyzing gold markets..."):
            gold_analysis = generate_ai_summary(
                "Gold", gold_price,
                gold_ind if "error" not in gold_ind else {},
                gold_cot, macro_data, gold_term
            )
            if gold_analysis:
                st.markdown(gold_analysis)
            else:
                st.warning("AI analysis unavailable. Add ANTHROPIC_API_KEY to .env file.")

with ai_col2:
    if st.button("🥈 Generate Silver Analysis", use_container_width=True, type="primary"):
        with st.spinner("Claude is analyzing silver markets..."):
            silver_analysis = generate_ai_summary(
                "Silver", silver_price,
                silver_ind if "error" not in silver_ind else {},
                silver_cot, macro_data, silver_term
            )
            if silver_analysis:
                st.markdown(silver_analysis)
            else:
                st.warning("AI analysis unavailable. Add ANTHROPIC_API_KEY to .env file.")

# === FOOTER ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown(f'<p class="timestamp">Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Data may be delayed</p>', unsafe_allow_html=True)

with st.expander("🔧 Debug: Raw API Responses"):
    d1, d2 = st.columns(2)
    with d1:
        st.write("**Gold Raw:**")
        st.code(str(gold_raw)[:500] if gold_raw else "No data")
    with d2:
        st.write("**Silver Raw:**")
        st.code(str(silver_raw)[:500] if silver_raw else "No data")
