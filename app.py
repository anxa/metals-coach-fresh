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
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from alpha_vantage_fetcher import (
    fetch_gold_price, fetch_silver_price, fetch_copper_price,
    fetch_platinum_price, fetch_palladium_price
)
from indicators import compute_indicators
from cot_fetcher import get_cot_summary
from macro_fetcher import get_macro_dashboard, get_copper_macro, analyze_macro_tailwind
from term_structure import analyze_term_structure
from ai_summary import generate_ai_summary, get_quick_verdict, get_copper_verdict
from market_regime import get_full_market_analysis, get_five_pillar_analysis
from forward_expectations import get_forward_expectations
from prediction_tracker import (
    auto_log_daily, update_actuals, get_accuracy_stats,
    get_recent_predictions, get_pending_count, is_market_closed
)
from cme_inventory import (
    get_latest_inventory, get_inventory_state, get_inventory_signal,
    get_inventory_trend, get_all_metals_summary, get_inventory_history_table
)
from pgm_ratio import analyze_ptpd_ratio, get_ratio_signal_text
from price_inventory_pressure import get_current_pressure, get_pressure_table_display
from daily_changes import get_all_changes, format_changes_html
from data_store import get_yesterday_spot_close, get_spot_high_and_days
from news_fetcher import fetch_all_news

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

# === CUSTOM CSS FOR PROFESSIONAL STYLING (GLASSMORPHISM) ===
st.markdown("""
<style>
    /* ===== FORCE DARK THEME EVERYWHERE ===== */
    :root {
        color-scheme: dark !important;
        --glass-bg: rgba(30, 37, 48, 0.6);
        --glass-border: rgba(255, 255, 255, 0.1);
        --glass-highlight: rgba(255, 255, 255, 0.05);
        --gold: #FFD700;
        --silver: #C0C0C0;
        --copper: #B87333;
        --platinum: #E5E4E2;
        --palladium: #CED0DD;
        --bullish: #00c853;
        --bearish: #ff5252;
        --neutral: #ffc107;
    }

    /* Main background - force dark on all devices */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"],
    .main, .block-container, [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0d12 0%, #111620 50%, #0e1117 100%) !important;
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
        background: var(--glass-bg) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        color: #ffffff !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
    }

    /* ===== GLASSMORPHISM TABS ===== */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-radius: 16px;
        padding: 8px !important;
        gap: 8px !important;
        justify-content: center !important;
        border: 1px solid var(--glass-border) !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }

    .stTabs [data-baseweb="tab"] {
        color: #aaa !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        padding: 12px 32px !important;
        border-radius: 12px !important;
        transition: all 0.3s ease !important;
        background: transparent !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #fff !important;
    }

    .stTabs [aria-selected="true"] {
        color: #000 !important;
        background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%) !important;
        box-shadow: 0 4px 20px rgba(255, 215, 0, 0.4), 0 0 40px rgba(255, 215, 0, 0.2) !important;
    }

    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }

    .stTabs [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* ===== GLASSMORPHISM STICKY NAV ===== */
    .sticky-nav {
        position: sticky;
        top: 0;
        z-index: 999;
        background: rgba(20, 25, 35, 0.85) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        padding: 10px 20px;
        border-bottom: 1px solid var(--glass-border);
        margin: -1rem -1rem 1rem -1rem;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
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

    /* ===== GLASSMORPHISM EXPANDERS ===== */
    .streamlit-expanderHeader {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(15px) !important;
        -webkit-backdrop-filter: blur(15px) !important;
        border-radius: 12px !important;
        border: 1px solid var(--glass-border) !important;
        color: #ffffff !important;
        transition: all 0.3s ease !important;
    }

    .streamlit-expanderHeader:hover {
        background: rgba(40, 50, 65, 0.7) !important;
        border-color: rgba(255, 255, 255, 0.15) !important;
    }

    .streamlit-expanderContent {
        background: rgba(20, 25, 35, 0.5) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border: 1px solid var(--glass-border) !important;
        border-top: none !important;
        border-radius: 0 0 12px 12px !important;
        color: #ffffff !important;
    }

    details summary span {
        color: #ffffff !important;
    }

    /* ===== HEADER STYLING ===== */
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
        text-shadow: 0 0 40px rgba(255, 215, 0, 0.3);
    }

    .sub-header {
        text-align: center;
        color: #b0b0b0 !important;
        font-size: 1.1rem;
        margin-top: -10px;
        margin-bottom: 30px;
    }

    /* ===== GLASSMORPHISM CARDS ===== */
    .metric-card {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid var(--glass-border);
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 var(--glass-highlight);
        margin-bottom: 16px;
        transition: all 0.3s ease;
    }

    .metric-card:hover {
        border-color: rgba(255, 255, 255, 0.2);
        box-shadow:
            0 12px 40px rgba(0, 0, 0, 0.4),
            inset 0 1px 0 var(--glass-highlight);
    }

    .metric-card-gold {
        border-left: 3px solid var(--gold);
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 var(--glass-highlight),
            -4px 0 20px rgba(255, 215, 0, 0.1);
    }

    .metric-card-silver {
        border-left: 3px solid var(--silver);
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 var(--glass-highlight),
            -4px 0 20px rgba(192, 192, 192, 0.1);
    }

    .metric-card-copper {
        border-left: 3px solid var(--copper);
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.3),
            inset 0 1px 0 var(--glass-highlight),
            -4px 0 20px rgba(184, 115, 51, 0.1);
    }

    /* Price display */
    .price-large {
        font-size: 2.5rem;
        font-weight: 700;
        color: #fff !important;
        margin: 0;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }

    .price-gold {
        color: var(--gold) !important;
        text-shadow: 0 0 20px rgba(255, 215, 0, 0.3);
    }

    .price-silver {
        color: var(--silver) !important;
        text-shadow: 0 0 20px rgba(192, 192, 192, 0.3);
    }

    .price-copper {
        color: var(--copper) !important;
        text-shadow: 0 0 20px rgba(184, 115, 51, 0.3);
    }

    /* Section headers */
    .section-header {
        font-size: 1.4rem;
        font-weight: 600;
        color: #fff !important;
        margin-top: 24px;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--glass-border);
    }

    /* ===== SIGNAL BADGES WITH GLOW ===== */
    .signal-bullish {
        background: linear-gradient(135deg, #00c853 0%, #00e676 100%);
        color: #000 !important;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        box-shadow: 0 0 15px rgba(0, 200, 83, 0.4);
    }

    .signal-bearish {
        background: linear-gradient(135deg, #ff1744 0%, #ff5252 100%);
        color: #fff !important;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        box-shadow: 0 0 15px rgba(255, 82, 82, 0.4);
    }

    .signal-neutral {
        background: linear-gradient(135deg, #ffc107 0%, #ffca28 100%);
        color: #000 !important;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
        box-shadow: 0 0 15px rgba(255, 193, 7, 0.4);
    }

    /* ===== SIGNAL DOTS WITH GLOW ===== */
    .signal-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 8px;
        animation: pulse 2s infinite;
    }

    .signal-dot-bullish {
        background: var(--bullish);
        box-shadow: 0 0 10px var(--bullish), 0 0 20px rgba(0, 200, 83, 0.5);
    }

    .signal-dot-bearish {
        background: var(--bearish);
        box-shadow: 0 0 10px var(--bearish), 0 0 20px rgba(255, 82, 82, 0.5);
    }

    .signal-dot-neutral {
        background: var(--neutral);
        box-shadow: 0 0 10px var(--neutral), 0 0 20px rgba(255, 193, 7, 0.5);
    }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.7; }
    }

    /* Data row styling */
    .data-row {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
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

    /* ===== GLASSMORPHISM VERDICT BOX ===== */
    .verdict-box {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 24px;
        text-align: center;
        border: 2px solid var(--glass-border);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }

    .verdict-bullish {
        border-color: var(--bullish) !important;
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.3),
            0 0 40px rgba(0, 200, 83, 0.15),
            inset 0 0 60px rgba(0, 200, 83, 0.05);
    }

    .verdict-bearish {
        border-color: var(--bearish) !important;
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.3),
            0 0 40px rgba(255, 82, 82, 0.15),
            inset 0 0 60px rgba(255, 82, 82, 0.05);
    }

    .verdict-neutral {
        border-color: var(--neutral) !important;
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.3),
            0 0 40px rgba(255, 193, 7, 0.15),
            inset 0 0 60px rgba(255, 193, 7, 0.05);
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

    /* ===== GLASSMORPHISM MACRO CARDS ===== */
    .macro-card {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        border: 1px solid var(--glass-border);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        transition: all 0.3s ease;
    }

    .macro-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
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
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, var(--glass-border) 50%, transparent 100%);
        margin: 40px 0;
    }

    /* ===== GLASSMORPHISM INFO BOX ===== */
    .info-box {
        background: rgba(255, 215, 0, 0.1) !important;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 215, 0, 0.3);
        border-radius: 12px;
        padding: 12px 16px;
        margin: 8px 0;
        color: #fff !important;
        box-shadow: 0 4px 20px rgba(255, 215, 0, 0.1);
    }

    /* Timestamp */
    .timestamp {
        text-align: center;
        color: #666 !important;
        font-size: 0.85rem;
        margin-top: 40px;
    }

    /* ===== GLASSMORPHISM BUTTONS ===== */
    .stButton button {
        background: var(--glass-bg) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        color: #fff !important;
        transition: all 0.3s ease !important;
    }

    .stButton button:hover {
        background: rgba(255, 215, 0, 0.2) !important;
        border-color: rgba(255, 215, 0, 0.4) !important;
        box-shadow: 0 0 20px rgba(255, 215, 0, 0.2) !important;
    }

    /* ===== PROGRESS/SCORE BAR ===== */
    .score-bar {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        height: 8px;
        overflow: hidden;
        margin: 8px 0;
    }

    .score-fill {
        height: 100%;
        border-radius: 10px;
        background: linear-gradient(90deg, var(--bullish) 0%, #00e676 100%);
        box-shadow: 0 0 10px var(--bullish);
        transition: width 0.5s ease;
    }

    .score-fill-bearish {
        background: linear-gradient(90deg, var(--bearish) 0%, #ff8a80 100%);
        box-shadow: 0 0 10px var(--bearish);
    }

    .score-fill-neutral {
        background: linear-gradient(90deg, var(--neutral) 0%, #ffe082 100%);
        box-shadow: 0 0 10px var(--neutral);
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
            backdrop-filter: blur(10px) !important;
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
    dot_class = get_signal_dot_class(signal_type)
    return f'<span class="{css_class}"><span class="signal-dot {dot_class}"></span>{text}</span>'


def get_signal_dot_class(signal):
    """Return CSS class for signal dot with glow effect."""
    if signal in ["bullish", "uptrend", "rising", "strong_buying", "buying"]:
        return "signal-dot-bullish"
    elif signal in ["bearish", "downtrend", "falling", "strong_selling", "selling"]:
        return "signal-dot-bearish"
    return "signal-dot-neutral"


def signal_emoji(signal):
    if signal in ["bullish", "uptrend", "rising", "strong_buying", "buying"]:
        return "🟢"
    elif signal in ["bearish", "downtrend", "falling", "strong_selling", "selling"]:
        return "🔴"
    elif signal in ["extreme_long", "extreme_short"]:
        return "🟡"
    return "⚪"


# === PLOTLY CHART HELPERS ===
METAL_COLORS = {
    "Gold": "#FFD700",
    "Silver": "#C0C0C0",
    "Copper": "#B87333",
    "Platinum": "#E5E4E2",
    "Palladium": "#CED0DD",
}


def create_price_chart(history_df, metal_name, height=300):
    """Create an interactive Plotly price chart with area fill."""
    if history_df is None or history_df.empty:
        return None

    color = METAL_COLORS.get(metal_name, "#FFD700")
    # Create rgba version for fill
    color_rgba = f"rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.15)"

    fig = go.Figure()

    # Add area trace
    fig.add_trace(go.Scatter(
        x=history_df.index,
        y=history_df['Close'],
        mode='lines',
        name=metal_name,
        line=dict(color=color, width=2),
        fill='tozeroy',
        fillcolor=color_rgba,
        hovertemplate='%{x|%b %d, %Y}<br>$%{y:,.2f}<extra></extra>'
    ))

    # Add SMA lines if available
    if 'SMA50' in history_df.columns:
        fig.add_trace(go.Scatter(
            x=history_df.index,
            y=history_df['SMA50'],
            mode='lines',
            name='SMA 50',
            line=dict(color='rgba(255,193,7,0.6)', width=1, dash='dot'),
            hovertemplate='SMA50: $%{y:,.2f}<extra></extra>'
        ))

    if 'SMA200' in history_df.columns:
        fig.add_trace(go.Scatter(
            x=history_df.index,
            y=history_df['SMA200'],
            mode='lines',
            name='SMA 200',
            line=dict(color='rgba(0,200,83,0.6)', width=1, dash='dot'),
            hovertemplate='SMA200: $%{y:,.2f}<extra></extra>'
        ))

    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#888'),
        xaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.05)',
            showline=False,
            zeroline=False,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(255,255,255,0.05)',
            showline=False,
            zeroline=False,
            side='right',
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1,
            bgcolor='rgba(0,0,0,0)',
        ),
        hovermode='x unified',
    )

    return fig


def create_rsi_gauge(value, height=180):
    """Create an RSI gauge meter."""
    if value is None:
        return None

    # Determine color based on RSI level
    if value >= 70:
        bar_color = "#ff5252"  # Overbought - red
    elif value <= 30:
        bar_color = "#00c853"  # Oversold - green
    else:
        bar_color = "#ffc107"  # Neutral - yellow

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={'suffix': '', 'font': {'size': 28, 'color': '#fff'}},
        gauge={
            'axis': {
                'range': [0, 100],
                'tickwidth': 1,
                'tickcolor': '#444',
                'tickfont': {'color': '#888', 'size': 10}
            },
            'bar': {'color': bar_color, 'thickness': 0.3},
            'bgcolor': 'rgba(0,0,0,0)',
            'borderwidth': 0,
            'steps': [
                {'range': [0, 30], 'color': 'rgba(0,200,83,0.15)'},
                {'range': [30, 70], 'color': 'rgba(255,193,7,0.1)'},
                {'range': [70, 100], 'color': 'rgba(255,82,82,0.15)'}
            ],
            'threshold': {
                'line': {'color': '#fff', 'width': 2},
                'thickness': 0.8,
                'value': value
            }
        },
        title={'text': 'RSI', 'font': {'size': 14, 'color': '#888'}}
    ))

    fig.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=40, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#fff'),
    )

    return fig


def create_sparkline(data, color, height=50, width=120):
    """Create a tiny sparkline chart for inline display."""
    if data is None or len(data) == 0:
        return None

    # Determine trend color
    if len(data) >= 2:
        trend_up = data.iloc[-1] > data.iloc[0]
        line_color = "#00c853" if trend_up else "#ff5252"
    else:
        line_color = color

    fig = go.Figure(go.Scatter(
        y=data.values,
        mode='lines',
        line=dict(color=line_color, width=1.5),
        fill='tozeroy',
        fillcolor=f'rgba({int(line_color[1:3], 16)}, {int(line_color[3:5], 16)}, {int(line_color[5:7], 16)}, 0.1)',
        hoverinfo='skip'
    ))

    fig.update_layout(
        height=height,
        width=width,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False, fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        showlegend=False,
    )

    return fig


def create_signal_bar(bullish_count, total=5, height=30):
    """Create a horizontal signal strength bar."""
    fig = go.Figure()

    # Background bar
    fig.add_trace(go.Bar(
        x=[total],
        y=['Signal'],
        orientation='h',
        marker=dict(color='rgba(255,255,255,0.1)'),
        hoverinfo='skip',
        showlegend=False,
    ))

    # Filled portion
    bar_color = "#00c853" if bullish_count >= 3 else "#ffc107" if bullish_count >= 2 else "#ff5252"
    fig.add_trace(go.Bar(
        x=[bullish_count],
        y=['Signal'],
        orientation='h',
        marker=dict(color=bar_color),
        hoverinfo='skip',
        showlegend=False,
    ))

    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False, range=[0, total], fixedrange=True),
        yaxis=dict(visible=False, fixedrange=True),
        barmode='overlay',
    )

    return fig


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
        copper_price, copper_raw = fetch_copper_price()
        platinum_price, platinum_raw = fetch_platinum_price()
        palladium_price, palladium_raw = fetch_palladium_price()

        progress.progress(25, text="Computing technical indicators...")
        gold_ind = compute_indicators("GC=F", spot_price=gold_price)
        silver_ind = compute_indicators("SI=F", spot_price=silver_price)
        copper_ind = compute_indicators("HG=F", spot_price=copper_price)
        platinum_ind = compute_indicators("PL=F", spot_price=platinum_price)
        palladium_ind = compute_indicators("PA=F", spot_price=palladium_price)

        progress.progress(45, text="Fetching COT positioning data...")
        try:
            gold_cot = get_cot_summary("GOLD")
            silver_cot = get_cot_summary("SILVER")
            copper_cot = get_cot_summary("COPPER")
            platinum_cot = get_cot_summary("PLATINUM")
            palladium_cot = get_cot_summary("PALLADIUM")
        except Exception as e:
            gold_cot = {"error": str(e)}
            silver_cot = {"error": str(e)}
            copper_cot = {"error": str(e)}
            platinum_cot = {"error": str(e)}
            palladium_cot = {"error": str(e)}

        progress.progress(65, text="Loading macro indicators...")
        try:
            macro_data = get_macro_dashboard()
        except Exception as e:
            macro_data = {"error": str(e), "indicators": {}}

        # Copper-specific macro (PMI data)
        try:
            copper_macro = get_copper_macro()
        except Exception as e:
            copper_macro = {"error": str(e), "indicators": {}}

        progress.progress(85, text="Analyzing term structure...")
        try:
            gold_term = analyze_term_structure("gold", spot_price=gold_price)
            silver_term = analyze_term_structure("silver", spot_price=silver_price)
            copper_term = analyze_term_structure("copper", spot_price=copper_price)
            platinum_term = analyze_term_structure("platinum", spot_price=platinum_price)
            palladium_term = analyze_term_structure("palladium", spot_price=palladium_price)
        except Exception as e:
            gold_term = {"error": str(e)}
            silver_term = {"error": str(e)}
            copper_term = {"error": str(e)}
            platinum_term = {"error": str(e)}
            palladium_term = {"error": str(e)}

        progress.progress(95, text="Running professional analysis...")
        # Professional regime analysis - old format (for backwards compatibility)
        try:
            macro_bias = macro_data.get("macro_bias", "neutral") if "error" not in macro_data else "neutral"
            gold_pro = get_full_market_analysis(gold_ind, macro_bias) if "error" not in gold_ind else {"error": "no data"}
            silver_pro = get_full_market_analysis(silver_ind, macro_bias) if "error" not in silver_ind else {"error": "no data"}
            # Copper uses its own macro (PMI-based)
            copper_bias = copper_macro.get("macro_bias", "neutral") if "error" not in copper_macro else "neutral"
            copper_pro = get_full_market_analysis(copper_ind, copper_bias) if "error" not in copper_ind else {"error": "no data"}
        except Exception as e:
            gold_pro = {"error": str(e)}
            silver_pro = {"error": str(e)}
            copper_pro = {"error": str(e)}

        # NEW: 5-pillar analysis
        try:
            # Get macro tailwind analysis
            macro_tailwind = analyze_macro_tailwind(macro_data) if "error" not in macro_data else {"status": "neutral"}

            # Run 5-pillar analysis
            gold_five = get_five_pillar_analysis(gold_ind, macro_tailwind, gold_cot) if "error" not in gold_ind else {"error": "no data"}
            silver_five = get_five_pillar_analysis(silver_ind, macro_tailwind, silver_cot) if "error" not in silver_ind else {"error": "no data"}
            # Copper uses simpler tailwind (PMI-based)
            copper_tailwind = {"status": copper_bias, "description": f"PMI-based macro: {copper_bias}"}
            copper_five = get_five_pillar_analysis(copper_ind, copper_tailwind, copper_cot) if "error" not in copper_ind else {"error": "no data"}
        except Exception as e:
            gold_five = {"error": str(e)}
            silver_five = {"error": str(e)}
            copper_five = {"error": str(e)}

        progress.progress(100, text="Complete!")
        progress.empty()

# === AUTO-LOG PREDICTIONS ===
# Automatically log daily predictions after market close (4pm ET)
try:
    if "error" not in gold_five and "error" not in silver_five:
        # Compute forward expectations for logging
        gold_exp = get_forward_expectations(gold_five, "gold")
        silver_exp = get_forward_expectations(silver_five, "silver")

        # Auto-log today's predictions (only if after market close)
        auto_log_daily(
            gold_five=gold_five,
            gold_exp=gold_exp,
            gold_price=gold_price,
            gold_indicators=gold_ind,
            silver_five=silver_five,
            silver_exp=silver_exp,
            silver_price=silver_price,
            silver_indicators=silver_ind
        )

        # Update any pending actuals
        update_actuals()
except Exception as e:
    pass  # Silent fail - don't block app if prediction tracking fails

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

FORWARD_EXPECTATIONS_GUIDE = """
**What this shows:** Historical outcomes when the market was in this same state (regime + momentum + participation combination).

**Key Metrics Explained:**

| Term | Meaning | How to Use |
|------|---------|------------|
| **Mean Return** | Average % gain/loss over the period | +0.5% mean = historically gained 0.5% on average |
| **Hit Rate** | % of times price went UP | 60% hit = price rose 60% of the time in this state |
| **Typical Range** | One standard deviation around median | Most outcomes fall within this range |
| **Observations** | Number of historical instances | More = more reliable (>50 is good) |
| **Confidence** | Overall reliability score (0-100) | Based on sample size + consistency + edge strength |

**Risk Metrics:**

| Term | Meaning | How to Use |
|------|---------|------------|
| **Avg Drawdown** | Typical dip BEFORE gains materialize | -1.5% = expect 1.5% pullback even in winning trades |
| **Risk/Reward** | Ratio of avg gain to avg drawdown | >1.0 = gains exceed typical pain; <1.0 = expect more pain than gain |

**Interpreting Hit Rate:**
- **>60%**: Strong directional edge - trade with confidence
- **55-60%**: Modest edge - use for confirmation, not primary signal
- **45-55%**: No edge - this state has no predictive value
- **<45%**: Bearish edge - historically went DOWN more often

**Important:** These are statistical tendencies, not predictions. A 60% hit rate means 40% of the time it went the other way!
"""

# Copper-specific guides
COPPER_MACRO_GUIDE = """
**China PMI (THE #1 DRIVER):** China consumes ~50% of global copper.
- PMI > 50 = Manufacturing expansion = BULLISH for copper
- PMI < 50 = Manufacturing contraction = BEARISH for copper

**US ISM PMI:** Secondary demand signal.
- > 50 = Expansion = BULLISH
- < 50 = Contraction = BEARISH

**USD/CNY:** Dollar strength vs Chinese yuan.
- Falling = Weaker dollar = BULLISH for commodities
- Rising = Stronger dollar = BEARISH for commodities
"""

COPPER_INVENTORY_GUIDE = """
**LME/COMEX Inventories are THE key short-term driver for copper.**

Unlike gold/silver (monetary metals), copper price is driven by physical supply/demand:
- **Falling inventories** = Physical tightness = BULLISH
- **Rising inventories** = Oversupply = BEARISH

📦 **Why it matters:** Low inventory = manufacturers competing for scarce supply = price rises
"""

# === STICKY NAVIGATION BAR ===
# Get quick verdict signals for nav bar
def get_nav_signal(ind, cot, macro, term, metal_type="standard"):
    """Get emoji for nav bar."""
    if "error" in ind:
        return "❓"
    if metal_type == "copper":
        verdict_data = get_copper_verdict(ind, cot, macro, term)
    else:
        verdict_data = get_quick_verdict(ind, cot, macro, term)
    verdict = verdict_data.get("verdict", "NEUTRAL")
    if "BULLISH" in verdict:
        return "🟢"
    elif "BEARISH" in verdict:
        return "🔴"
    return "🟡"

gold_nav = get_nav_signal(gold_ind, gold_cot, macro_data, gold_term)
silver_nav = get_nav_signal(silver_ind, silver_cot, macro_data, silver_term)
copper_nav = get_nav_signal(copper_ind, copper_cot, copper_macro, copper_term, "copper")
platinum_nav = get_nav_signal(platinum_ind, platinum_cot, macro_data, platinum_term)
palladium_nav = get_nav_signal(palladium_ind, palladium_cot, macro_data, palladium_term)

st.markdown(f"""
<div class="sticky-nav">
    <div style="display: flex; justify-content: center; align-items: center; gap: 24px; flex-wrap: wrap;">
        <span style="font-size: 0.95rem; color: #fff;">
            <strong>Gold</strong> {gold_nav}
        </span>
        <span style="color: #444;">|</span>
        <span style="font-size: 0.95rem; color: #fff;">
            <strong>Silver</strong> {silver_nav}
        </span>
        <span style="color: #444;">|</span>
        <span style="font-size: 0.95rem; color: #fff;">
            <strong>Copper</strong> {copper_nav}
        </span>
        <span style="color: #444;">|</span>
        <span style="font-size: 0.95rem; color: #fff;">
            <strong>Platinum</strong> {platinum_nav}
        </span>
        <span style="color: #444;">|</span>
        <span style="font-size: 0.95rem; color: #fff;">
            <strong>Palladium</strong> {palladium_nav}
        </span>
        <span style="color: #444; margin-left: 16px;">|</span>
        <span style="font-size: 0.85rem; color: #888;">
            Updated: {datetime.now().strftime("%H:%M")}
        </span>
    </div>
</div>
""", unsafe_allow_html=True)

# === WHAT CHANGED TODAY ===
# Get pressure data for change detection
try:
    gold_pressure_data = get_current_pressure("gold")
    silver_pressure_data = get_current_pressure("silver")
    copper_pressure_data = get_current_pressure("copper")
    platinum_pressure_data = get_current_pressure("platinum")
    palladium_pressure_data = get_current_pressure("palladium")
except Exception:
    gold_pressure_data = {"error": "unavailable"}
    silver_pressure_data = {"error": "unavailable"}
    copper_pressure_data = {"error": "unavailable"}
    platinum_pressure_data = {"error": "unavailable"}
    palladium_pressure_data = {"error": "unavailable"}

# Detect changes across all metals (pass spot prices for accurate daily change %)
daily_changes = get_all_changes(
    gold_ind, silver_ind, copper_ind,
    platinum_ind, palladium_ind,
    copper_pressure_data, platinum_pressure_data, palladium_pressure_data,
    gold_price, silver_price, copper_price, platinum_price, palladium_price
)

# Display the changes section
changes_html = format_changes_html(daily_changes)
st.markdown(changes_html, unsafe_allow_html=True)

# === MARKET NEWS ===
@st.cache_data(ttl=900)  # Cache for 15 minutes
def get_cached_news():
    return fetch_all_news(limit_per_metal=4)

try:
    news_items = get_cached_news()
except Exception:
    news_items = []

if news_items:
    # Build news items HTML with escaped titles
    import html as html_lib
    news_items_html = ""
    for item in news_items[:10]:
        border_color = '#FFD700' if item['metal'] == 'gold' else '#C0C0C0' if item['metal'] == 'silver' else '#E5E4E2'
        safe_title = html_lib.escape(item['title'])
        safe_url = html_lib.escape(item['url'])
        news_items_html += f'''<a href="{safe_url}" target="_blank" rel="noopener noreferrer" class="news-item" style="text-decoration: none; display: block; margin-bottom: 8px;">
<div style="background: rgba(255,255,255,0.03); border-radius: 8px; padding: 10px 14px; display: flex; align-items: center; border-left: 3px solid {border_color};">
<span style="margin-right: 10px;">{item['emoji']}</span>
<span style="color: #e0e0e0; flex: 1; font-size: 0.9rem;">{safe_title}</span>
<span style="color: #666; font-size: 0.75rem; margin-left: 10px; white-space: nowrap;">{item['date_str']}</span>
</div></a>'''

    st.markdown(f"""
<div style="background: rgba(30, 37, 48, 0.6); backdrop-filter: blur(20px); border-radius: 16px; padding: 20px; margin: 16px 0; border: 1px solid rgba(255, 255, 255, 0.1);">
<div style="color: #888; font-size: 0.9rem; margin-bottom: 12px;">📰 Precious Metals News</div>
{news_items_html}
<div style="text-align: right; margin-top: 12px;">
<a href="https://www.metalsdaily.com/news/" target="_blank" rel="noopener noreferrer" style="color: #888; font-size: 0.8rem; text-decoration: none;">More news →</a>
</div>
</div>
""", unsafe_allow_html=True)

# === HERO SECTION - LIVE PRICES ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

hero_col1, hero_col2, hero_col3 = st.columns(3)

with hero_col1:
    if gold_price:
        # Use spot-based high with dynamic label showing days of data
        gold_high, gold_days = get_spot_high_and_days("XAU")
        if gold_high and gold_days > 0:
            pct_from_high = ((gold_price / gold_high) - 1) * 100
            high_label = f"{gold_days}d high"
        else:
            pct_from_high = gold_ind.get('pct_from_52w_high', 0) if "error" not in gold_ind else 0
            high_label = "52w high"
        trend = gold_ind.get('trend', 'unknown') if "error" not in gold_ind else 'unknown'

        st.markdown(f"""
        <div class="metric-card metric-card-gold">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #888; font-size: 0.9rem;">GOLD (XAU/USD)</span>
                    <h2 class="price-large price-gold">{format_price(gold_price)}</h2>
                    <span style="color: {'#00c853' if pct_from_high >= 0 else '#ff5252'}; font-size: 0.95rem;">
                        {pct_from_high:+.2f}% from {high_label}
                    </span>
                </div>
                <div style="text-align: right;">
                    {signal_badge(trend.upper(), trend)}
                    <p style="color: #666; font-size: 0.8rem; margin-top: 8px;">Source: Gold-API</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Sparkline for 20-day trend
        if "error" not in gold_ind:
            gold_hist = gold_ind.get("history")
            if gold_hist is not None and len(gold_hist) >= 20:
                sparkline_data = gold_hist['Close'].tail(20)
                sparkline = create_sparkline(sparkline_data, "#FFD700", height=40, width=None)
                if sparkline:
                    st.plotly_chart(sparkline, use_container_width=True, config={'displayModeBar': False})
    else:
        st.error("Gold price unavailable")

with hero_col2:
    if silver_price:
        # Use spot-based high with dynamic label showing days of data
        silver_high, silver_days = get_spot_high_and_days("XAG")
        if silver_high and silver_days > 0:
            pct_from_high = ((silver_price / silver_high) - 1) * 100
            high_label = f"{silver_days}d high"
        else:
            pct_from_high = silver_ind.get('pct_from_52w_high', 0) if "error" not in silver_ind else 0
            high_label = "52w high"
        trend = silver_ind.get('trend', 'unknown') if "error" not in silver_ind else 'unknown'

        st.markdown(f"""
        <div class="metric-card metric-card-silver">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #888; font-size: 0.9rem;">SILVER (XAG/USD)</span>
                    <h2 class="price-large price-silver">{format_price(silver_price)}</h2>
                    <span style="color: {'#00c853' if pct_from_high >= 0 else '#ff5252'}; font-size: 0.95rem;">
                        {pct_from_high:+.2f}% from {high_label}
                    </span>
                </div>
                <div style="text-align: right;">
                    {signal_badge(trend.upper(), trend)}
                    <p style="color: #666; font-size: 0.8rem; margin-top: 8px;">Source: Gold-API</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Sparkline for 20-day trend
        if "error" not in silver_ind:
            silver_hist = silver_ind.get("history")
            if silver_hist is not None and len(silver_hist) >= 20:
                sparkline_data = silver_hist['Close'].tail(20)
                sparkline = create_sparkline(sparkline_data, "#C0C0C0", height=40, width=None)
                if sparkline:
                    st.plotly_chart(sparkline, use_container_width=True, config={'displayModeBar': False})
    else:
        st.error("Silver price unavailable")

with hero_col3:
    if copper_price:
        # Use spot-based high with dynamic label showing days of data
        copper_high, copper_days = get_spot_high_and_days("HG")
        if copper_high and copper_days > 0:
            pct_from_high = ((copper_price / copper_high) - 1) * 100
            high_label = f"{copper_days}d high"
        else:
            pct_from_high = copper_ind.get('pct_from_52w_high', 0) if "error" not in copper_ind else 0
            high_label = "52w high"
        trend = copper_ind.get('trend', 'unknown') if "error" not in copper_ind else 'unknown'

        st.markdown(f"""
        <div class="metric-card metric-card-copper">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: #888; font-size: 0.9rem;">COPPER (HG/USD)</span>
                    <h2 class="price-large price-copper">{format_price(copper_price)}/lb</h2>
                    <span style="color: {'#00c853' if pct_from_high >= 0 else '#ff5252'}; font-size: 0.95rem;">
                        {pct_from_high:+.2f}% from {high_label}
                    </span>
                </div>
                <div style="text-align: right;">
                    {signal_badge(trend.upper(), trend)}
                    <p style="color: #666; font-size: 0.8rem; margin-top: 8px;">Source: Gold-API</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Sparkline for 20-day trend
        if "error" not in copper_ind:
            copper_hist = copper_ind.get("history")
            if copper_hist is not None and len(copper_hist) >= 20:
                sparkline_data = copper_hist['Close'].tail(20)
                sparkline = create_sparkline(sparkline_data, "#B87333", height=40, width=None)
                if sparkline:
                    st.plotly_chart(sparkline, use_container_width=True, config={'displayModeBar': False})
    else:
        st.error("Copper price unavailable")

# === PROFESSIONAL 5-PILLAR ANALYSIS ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown("### 📈 Professional Market Analysis")
st.caption("5-pillar framework with clear rules. Trade transitions, not snapshots.")


def get_pillar_color(status: str) -> tuple:
    """Get color and emoji for pillar status."""
    status_lower = status.lower() if status else ""
    if status_lower in ["uptrend", "accelerating", "confirming", "supportive", "washed_out", "light_positioning"]:
        return "#00c853", "🟢"
    elif status_lower in ["downtrend", "cooling", "thinning", "distribution", "hostile", "crowded_long"]:
        return "#ff5252", "🔴"
    elif status_lower in ["diverging", "mixed", "elevated_long"]:
        return "#ffc107", "🟡"
    else:
        return "#607d8b", "⚪"


def render_five_pillar_analysis(five_data: dict, metal_name: str, color: str):
    """Render new 5-pillar professional analysis."""
    if "error" in five_data:
        st.warning(f"{metal_name} 5-pillar analysis unavailable")
        return

    regime = five_data.get("regime", {})
    momentum = five_data.get("momentum", {})
    participation = five_data.get("participation", {})
    tailwind = five_data.get("tailwind", {})
    positioning = five_data.get("positioning", {})
    assessment = five_data.get("assessment", {})

    # Overall assessment banner
    bias = assessment.get("bias", "neutral")
    action = assessment.get("action", "No recommendation")
    bullish_count = assessment.get("bullish_signals", 0)
    bearish_count = assessment.get("bearish_signals", 0)

    if "bullish" in bias:
        box_color = "#00c853"
        bias_emoji = "🟢"
    elif "bearish" in bias:
        box_color = "#ff5252"
        bias_emoji = "🔴"
    else:
        box_color = "#ffc107"
        bias_emoji = "⚪"

    # Calculate score percentage for visual bar
    total_signals = bullish_count + bearish_count
    score_pct = (bullish_count / 5) * 100 if total_signals > 0 else 50

    # Determine bar color class
    if "bullish" in bias:
        bar_class = ""
    elif "bearish" in bias:
        bar_class = "score-fill-bearish"
    else:
        bar_class = "score-fill-neutral"

    text_color = '#000' if 'bullish' in bias else '#fff'
    bias_label = bias.upper().replace('_', ' ')

    # Full-width status banner at top
    card_html = f'''<div style="background: rgba(30, 37, 48, 0.6); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-radius: 16px; overflow: hidden; border: 1px solid rgba(255, 255, 255, 0.1); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3); margin-bottom: 16px;">
<div style="background: linear-gradient(90deg, {box_color} 0%, {box_color}99 100%); padding: 10px 20px; display: flex; justify-content: space-between; align-items: center;">
<span style="color: {text_color}; font-weight: 700; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;">{bias_emoji} {bias_label}</span>
<span style="color: {text_color}; font-size: 0.85rem; opacity: 0.9;">{bullish_count}/5 Bullish Signals</span>
</div>
<div style="padding: 20px; border-left: 3px solid {color};">
<div style="color: #888; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px;">{metal_name}</div>
<div style="font-size: 1.1rem; color: #fff; font-weight: 500;">{action}</div>
<div style="margin-top: 16px;">
<div class="score-bar" style="height: 6px;"><div class="score-fill {bar_class}" style="width: {score_pct}%;"></div></div>
<div style="display: flex; justify-content: space-between; margin-top: 6px;">
<span style="color: #888; font-size: 0.7rem;">Bearish</span>
<span style="color: #888; font-size: 0.7rem;">Bullish</span>
</div>
</div>
</div>
</div>'''
    st.markdown(card_html, unsafe_allow_html=True)

    # 5 Pillars display
    with st.expander(f"View {metal_name} 5-Pillar Details"):
        # Pillar 1: REGIME
        regime_status = regime.get("regime", "unknown")
        regime_color, regime_emoji = get_pillar_color(regime_status)
        st.markdown(f"**1. REGIME:** {regime_emoji} `{regime_status.upper()}`")
        st.caption(regime.get("description", ""))
        for cond in regime.get("conditions", [])[:3]:  # Show first 3 conditions
            st.caption(f"  • {cond}")
        st.markdown("---")

        # Pillar 2: MOMENTUM
        mom_phase = momentum.get("phase", "unknown")
        mom_color, mom_emoji = get_pillar_color(mom_phase)
        st.markdown(f"**2. MOMENTUM:** {mom_emoji} `{mom_phase.upper()}`")
        st.caption(momentum.get("description", ""))
        if momentum.get("divergence_type"):
            st.warning(f"⚠️ {momentum['divergence_type'].upper()} DIVERGENCE")
        for cond in momentum.get("conditions", [])[:3]:
            st.caption(f"  • {cond}")
        st.markdown("---")

        # Pillar 3: PARTICIPATION
        part_status = participation.get("status", "unknown")
        part_color, part_emoji = get_pillar_color(part_status)
        st.markdown(f"**3. PARTICIPATION:** {part_emoji} `{part_status.upper()}`")
        st.caption(participation.get("description", ""))
        for cond in participation.get("conditions", [])[:3]:
            st.caption(f"  • {cond}")
        st.markdown("---")

        # Pillar 4: MACRO TAILWIND
        tail_status = tailwind.get("status", "neutral")
        tail_color, tail_emoji = get_pillar_color(tail_status)
        st.markdown(f"**4. MACRO TAILWIND:** {tail_emoji} `{tail_status.upper()}`")
        st.caption(tailwind.get("description", ""))
        for cond in tailwind.get("conditions", [])[:3]:
            st.caption(f"  • {cond}")
        st.markdown("---")

        # Pillar 5: POSITIONING
        pos_status = positioning.get("status", "unknown")
        pos_color, pos_emoji = get_pillar_color(pos_status)
        st.markdown(f"**5. POSITIONING:** {pos_emoji} `{pos_status.upper()}`")
        st.caption(positioning.get("description", ""))
        if positioning.get("warning"):
            st.warning(f"⚠️ {positioning['warning']}")
        for cond in positioning.get("conditions", [])[:2]:
            st.caption(f"  • {cond}")

        # Warnings
        if assessment.get("warnings"):
            st.markdown("---")
            st.markdown("**⚠️ Key Warnings:**")
            for warn in assessment["warnings"]:
                st.warning(warn)


pro_col1, pro_col2, pro_col3 = st.columns(3)

with pro_col1:
    render_five_pillar_analysis(gold_five, "GOLD", "#FFD700")

with pro_col2:
    render_five_pillar_analysis(silver_five, "SILVER", "#C0C0C0")

with pro_col3:
    render_five_pillar_analysis(copper_five, "COPPER", "#B87333")

# === FORWARD EXPECTATIONS ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown("### 🎯 Forward Expectations")
st.caption("Probabilistic outlook based on historical state outcomes. Not predictions - statistical tendencies.")

with st.expander("ℹ️ Understanding Forward Expectations", expanded=False):
    st.markdown(FORWARD_EXPECTATIONS_GUIDE)


def get_direction_color(direction: str) -> tuple:
    """Get color and emoji for expected direction."""
    if direction in ["strongly_positive", "positive"]:
        return "#00c853", "🟢"
    elif direction in ["strongly_negative", "negative"]:
        return "#ff5252", "🔴"
    else:
        return "#ffc107", "⚪"


def render_forward_expectations(five_pillar: dict, metal: str, color: str):
    """Render forward expectations for a metal based on current 5-pillar state."""
    expectations = get_forward_expectations(five_pillar, metal.lower())

    if not expectations.get("has_data"):
        st.info(f"Run backtest for {metal} to enable forward expectations")
        return

    state = expectations["state_readable"]
    n_samples = expectations["n_samples"]
    confidence = expectations["confidence_score"]
    edge_class = expectations.get("edge_class", "neutral")

    exp_5d = expectations["expectations"]["5d"]
    exp_20d = expectations["expectations"]["20d"]
    risk = expectations["risk_metrics"]

    # Direction colors
    dir_5d_color, dir_5d_emoji = get_direction_color(exp_5d["direction"])
    dir_20d_color, dir_20d_emoji = get_direction_color(exp_20d["direction"])

    # Header with state and confidence
    st.markdown(f"""
    <div style="background: linear-gradient(145deg, #1a2332 0%, #1e2940 100%);
                border-radius: 12px; padding: 16px; border-left: 4px solid {color};
                margin-bottom: 12px;">
        <div style="color: #888; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px;">{metal}</div>
        <div style="font-size: 0.95rem; color: #fff; margin: 6px 0;">{state}</div>
        <div style="display: flex; gap: 12px; margin-top: 8px;">
            <span style="color: #888; font-size: 0.8rem;">📊 {n_samples} observations</span>
            <span style="color: #888; font-size: 0.8rem;">🎯 {confidence:.0f}% confidence</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Expectations
    col_5d, col_20d = st.columns(2)

    with col_5d:
        st.markdown(f"""
        <div style="background: #1a2332; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="color: #888; font-size: 0.75rem;">5-DAY OUTLOOK</div>
            <div style="font-size: 1.3rem; color: {dir_5d_color}; font-weight: bold;">{dir_5d_emoji} {exp_5d['direction'].replace('_', ' ').upper()}</div>
            <div style="color: #aaa; font-size: 0.8rem; margin-top: 4px;">
                Mean: {exp_5d['mean']:+.2f}% | Hit: {exp_5d['hit_rate']:.0f}%
            </div>
            <div style="color: #666; font-size: 0.75rem;">
                Range: {exp_5d['typical_range'][0]:+.1f}% to {exp_5d['typical_range'][1]:+.1f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_20d:
        st.markdown(f"""
        <div style="background: #1a2332; border-radius: 8px; padding: 12px; text-align: center;">
            <div style="color: #888; font-size: 0.75rem;">20-DAY OUTLOOK</div>
            <div style="font-size: 1.3rem; color: {dir_20d_color}; font-weight: bold;">{dir_20d_emoji} {exp_20d['direction'].replace('_', ' ').upper()}</div>
            <div style="color: #aaa; font-size: 0.8rem; margin-top: 4px;">
                Mean: {exp_20d['mean']:+.2f}% | Hit: {exp_20d['hit_rate']:.0f}%
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Risk metrics and warnings in expander
    with st.expander(f"View {metal} Risk & Warnings"):
        st.markdown("**Risk Profile:**")
        st.caption(f"• Avg drawdown before gains: {risk['avg_drawdown_5d']:.1f}%")
        st.caption(f"• Risk/Reward ratio: {risk['risk_reward_ratio']:.2f}")

        warnings = expectations.get("warnings", [])
        if warnings:
            st.markdown("**Warnings:**")
            for w in warnings[:3]:
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(w["severity"], "⚪")
                st.caption(f"{severity_icon} {w['message']}")

        inv = expectations.get("invalidation", {})
        if inv:
            st.markdown("**Invalidation:**")
            st.caption(f"• {inv.get('trigger', 'N/A')}")
            st.caption(f"• {inv.get('suggested_stop', '')}")


# Render expectations for each metal
fwd_col1, fwd_col2, fwd_col3 = st.columns(3)

with fwd_col1:
    if "error" not in gold_five:
        render_forward_expectations(gold_five, "GOLD", "#FFD700")
    else:
        st.info("Gold forward expectations unavailable")

with fwd_col2:
    if "error" not in silver_five:
        render_forward_expectations(silver_five, "SILVER", "#C0C0C0")
    else:
        st.info("Silver forward expectations unavailable")

with fwd_col3:
    # Copper doesn't have backtest data yet
    st.info("Copper forward expectations require backtest data")

# === PREDICTION TRACKING ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown("### 📝 Prediction Tracking")

# Status bar
try:
    pending = get_pending_count()
    stats = get_accuracy_stats()
    market_status = "After market close" if is_market_closed() else "Market open - logging at 4pm ET"

    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        st.caption(f"📊 Total predictions: {stats['total_predictions']}")
    with status_col2:
        st.caption(f"⏳ Pending actuals: 5d={pending['pending_5d']} | 20d={pending['pending_20d']}")
    with status_col3:
        st.caption(f"🕐 {market_status}")
except Exception:
    st.caption("Prediction tracking initializing...")

with st.expander("📊 Prediction Accuracy Dashboard", expanded=False):
    try:
        stats = get_accuracy_stats()

        if stats["total_predictions"] == 0:
            st.info("No predictions logged yet. Predictions are automatically logged after market close (4pm ET).")
        else:
            # Overall stats
            st.markdown("**Overall Accuracy:**")
            acc_col1, acc_col2, acc_col3, acc_col4 = st.columns(4)

            with acc_col1:
                acc_5d = stats.get("accuracy_5d")
                if acc_5d is not None:
                    color = "#00c853" if acc_5d >= 50 else "#ff5252"
                    st.markdown(f"""
                    <div style="background: #1a2332; border-radius: 8px; padding: 12px; text-align: center;">
                        <div style="color: #888; font-size: 0.75rem;">5-DAY ACCURACY</div>
                        <div style="font-size: 1.5rem; color: {color}; font-weight: bold;">{acc_5d:.0f}%</div>
                        <div style="color: #666; font-size: 0.7rem;">{stats['predictions_with_5d_actuals']} measured</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.metric("5-Day Accuracy", "N/A", help="Need at least 5 days of data")

            with acc_col2:
                acc_20d = stats.get("accuracy_20d")
                if acc_20d is not None:
                    color = "#00c853" if acc_20d >= 50 else "#ff5252"
                    st.markdown(f"""
                    <div style="background: #1a2332; border-radius: 8px; padding: 12px; text-align: center;">
                        <div style="color: #888; font-size: 0.75rem;">20-DAY ACCURACY</div>
                        <div style="font-size: 1.5rem; color: {color}; font-weight: bold;">{acc_20d:.0f}%</div>
                        <div style="color: #666; font-size: 0.7rem;">{stats['predictions_with_20d_actuals']} measured</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.metric("20-Day Accuracy", "N/A", help="Need at least 20 days of data")

            with acc_col3:
                inv_rate = stats.get("invalidation_rate")
                if inv_rate is not None:
                    st.markdown(f"""
                    <div style="background: #1a2332; border-radius: 8px; padding: 12px; text-align: center;">
                        <div style="color: #888; font-size: 0.75rem;">INVALIDATION RATE</div>
                        <div style="font-size: 1.5rem; color: #ffc107; font-weight: bold;">{inv_rate:.0f}%</div>
                        <div style="color: #666; font-size: 0.7rem;">hit stop before target</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.metric("Invalidation Rate", "N/A")

            with acc_col4:
                acc_excl = stats.get("accuracy_excluding_invalidated")
                if acc_excl is not None:
                    color = "#00c853" if acc_excl >= 50 else "#ff5252"
                    st.markdown(f"""
                    <div style="background: #1a2332; border-radius: 8px; padding: 12px; text-align: center;">
                        <div style="color: #888; font-size: 0.75rem;">ACCURACY (EXCL. INVALIDATED)</div>
                        <div style="font-size: 1.5rem; color: {color}; font-weight: bold;">{acc_excl:.0f}%</div>
                        <div style="color: #666; font-size: 0.7rem;">20d without stops hit</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.metric("Acc. (excl. inv.)", "N/A")

            # Recent predictions table
            st.markdown("---")
            st.markdown("**Recent Predictions:**")
            recent = get_recent_predictions(10)

            if not recent.empty:
                # Format for display
                display_df = recent.copy()
                display_df["date"] = display_df["date"].dt.strftime("%Y-%m-%d")
                display_df["spot_price"] = display_df["spot_price"].apply(lambda x: f"${x:,.2f}" if x else "N/A")
                display_df["exp_5d_mean"] = display_df["exp_5d_mean"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A")
                display_df["actual_5d_return"] = display_df["actual_5d_return"].apply(lambda x: f"{x:+.2f}%" if pd.notna(x) else "pending")
                display_df["direction_correct_5d"] = display_df["direction_correct_5d"].apply(
                    lambda x: "✅" if x == True else ("❌" if x == False else "⏳")
                )
                display_df["was_invalidated"] = display_df["was_invalidated"].apply(
                    lambda x: "🛑 Yes" if x == True else ("No" if x == False else "⏳")
                )

                # Rename columns for display
                display_df = display_df.rename(columns={
                    "date": "Date",
                    "metal": "Metal",
                    "spot_price": "Price",
                    "regime": "Regime",
                    "exp_5d_mean": "Exp 5D",
                    "actual_5d_return": "Actual 5D",
                    "direction_correct_5d": "Correct?",
                    "was_invalidated": "Invalidated?"
                })

                st.dataframe(
                    display_df[["Date", "Metal", "Price", "Regime", "Exp 5D", "Actual 5D", "Correct?", "Invalidated?"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No predictions to display yet.")
    except Exception as e:
        st.error(f"Error loading accuracy data: {str(e)}")

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

# === METAL ANALYSIS ACCORDIONS ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown("### 📊 Metal Analysis")
st.markdown('<p class="metal-selector-header">Expand any metal for detailed technical analysis</p>', unsafe_allow_html=True)


def get_verdict_info(ind, cot, macro, term, metal_type="standard"):
    """Get verdict info for accordion header."""
    if "error" in ind:
        return "❓", "UNKNOWN", "#888"

    if metal_type == "copper":
        verdict_data = get_copper_verdict(ind, cot, macro, term)
    else:
        verdict_data = get_quick_verdict(ind, cot, macro, term)

    verdict = verdict_data.get("verdict", "NEUTRAL")

    if "BULLISH" in verdict:
        return "🟢", verdict, "#00c853"
    elif "BEARISH" in verdict:
        return "🔴", verdict, "#ff5252"
    else:
        return "🟡", verdict, "#ffc107"


def get_daily_change(symbol: str, spot_price: float = None, ind: dict = None):
    """
    Get daily price change percentage using spot-to-spot comparison.

    Compares today's live spot price against yesterday's spot close from
    Gold-API history for accurate daily change calculation.

    Falls back to futures data if spot history isn't available (e.g., platinum).

    Args:
        symbol: Metal symbol (XAU, XAG, HG, XPT, XPD)
        spot_price: Current live spot price from Gold-API
        ind: Indicator dict with futures history (fallback for metals like platinum)

    Returns:
        Percentage change as float, or None if unavailable
    """
    if spot_price is None:
        return None

    # Try spot-to-spot comparison first (most accurate)
    yesterday_close = get_yesterday_spot_close(symbol)
    if yesterday_close is not None:
        return ((spot_price / yesterday_close) - 1) * 100

    # Fallback to futures data for metals without spot history (e.g., platinum)
    if ind is not None and "error" not in ind:
        hist = ind.get("history")
        if hist is not None and len(hist) >= 2:
            # Use yesterday's futures close as fallback
            yesterday_futures = hist["Close"].iloc[-2]
            return ((spot_price / yesterday_futures) - 1) * 100

    return None


# Prepare accordion header data for all metals
gold_emoji, gold_verdict_text, gold_color = get_verdict_info(gold_ind, gold_cot, macro_data, gold_term)
silver_emoji, silver_verdict_text, silver_color = get_verdict_info(silver_ind, silver_cot, macro_data, silver_term)
copper_emoji, copper_verdict_text, copper_color = get_verdict_info(copper_ind, copper_cot, copper_macro, copper_term, "copper")
platinum_emoji, platinum_verdict_text, platinum_color = get_verdict_info(platinum_ind, platinum_cot, macro_data, platinum_term)
palladium_emoji, palladium_verdict_text, palladium_color = get_verdict_info(palladium_ind, palladium_cot, macro_data, palladium_term)

# Get daily changes - use spot history, with futures fallback for platinum
gold_change = get_daily_change("XAU", gold_price)
silver_change = get_daily_change("XAG", silver_price)
copper_change = get_daily_change("HG", copper_price)
platinum_change = get_daily_change("XPT", platinum_price, platinum_ind)  # Futures fallback
palladium_change = get_daily_change("XPD", palladium_price)

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

        # Build price levels table - only show Futures row if we have futures data
        futures_price = ind.get('futures_price')
        futures_row = f"| **Futures** | {format_price(futures_price)} |\n        " if futures_price else ""

        st.markdown(f"""
        | Level | Price |
        |-------|-------|
        | **Spot** | {format_price(ind.get('spot_price') or ind.get('last_close'))} |
        {futures_row}| **All-Time High** | {format_price(ind.get('ath'))} |
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
        st.markdown("#### ⚡ Momentum Signals")
        with st.expander("ℹ️ What to look for"):
            st.markdown(MOMENTUM_GUIDE)

        # RSI with trajectory analysis
        rsi_val = ind.get('rsi14')
        rsi_momentum = ind.get('rsi_momentum', {})
        rsi_signal_type = rsi_momentum.get('signal_type', 'neutral')
        rsi_action = rsi_momentum.get('signal', 'N/A')

        # MACD with trajectory analysis
        macd_momentum = ind.get('macd_momentum', {})
        macd_signal_type = macd_momentum.get('signal_type', 'neutral')
        macd_action = macd_momentum.get('signal', 'N/A')

        # OBV with divergence detection
        obv_momentum = ind.get('obv_momentum', {})
        obv_signal_type = obv_momentum.get('signal_type', 'neutral')
        obv_action = obv_momentum.get('signal', 'N/A')
        obv_divergence = obv_momentum.get('divergence')

        vol_ratio = ind.get('volume_ratio')
        vol_signal = ind.get('volume_signal', 'N/A')

        # RSI Section with Gauge
        rsi_col1, rsi_col2 = st.columns([1, 1])
        with rsi_col1:
            if rsi_val is not None:
                rsi_gauge = create_rsi_gauge(rsi_val, height=150)
                if rsi_gauge:
                    st.plotly_chart(rsi_gauge, use_container_width=True, config={'displayModeBar': False})
            else:
                st.markdown("**RSI(14):** N/A")
        with rsi_col2:
            st.markdown("**RSI Analysis**")
            if "error" not in rsi_momentum:
                rsi_change = rsi_momentum.get('change', 0)
                rsi_dir = "↑" if rsi_change > 0 else "↓" if rsi_change < 0 else "→"
                st.caption(f"{rsi_dir} {abs(rsi_change):.1f} pts (5-day)")
                st.markdown(f"{signal_emoji(rsi_signal_type)} {rsi_action}", unsafe_allow_html=True)
            if rsi_val is not None:
                if rsi_val >= 70:
                    st.caption("⚠️ Overbought territory")
                elif rsi_val <= 30:
                    st.caption("💡 Oversold territory")
        st.markdown("---")

        # MACD Section
        st.markdown(f"**MACD:** {ind.get('macd_crossover', 'N/A')}")
        if "error" not in macd_momentum:
            hist_status = macd_momentum.get('histogram_status', 'unknown')
            crossover = macd_momentum.get('crossover_detected', False)
            if crossover:
                bars = macd_momentum.get('bars_since_crossover', 0)
                st.caption(f"Crossover {bars} bar(s) ago")
            st.markdown(f"{signal_emoji(macd_signal_type)} {macd_action}", unsafe_allow_html=True)
        st.markdown("---")

        # OBV Section
        st.markdown(f"**OBV:** {ind.get('obv_trend', 'N/A')}")
        if "error" not in obv_momentum:
            if obv_divergence:
                st.warning(f"⚠️ {obv_divergence.upper()} DIVERGENCE DETECTED")
            st.markdown(f"{signal_emoji(obv_signal_type)} {obv_action}", unsafe_allow_html=True)
        st.markdown("---")

        # Volume
        st.markdown(f"**Volume:** {format_number(vol_ratio, 2) if vol_ratio else 'N/A'}x avg ({vol_signal})")

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

    # Price Chart - Interactive Plotly
    st.markdown("#### 📉 Price Chart (180 Days)")
    hist = ind.get("history")
    if hist is not None and not hist.empty:
        chart_df = hist.tail(180).copy()
        # Add SMA columns if available
        if ind.get('sma50') is not None and 'Close' in chart_df.columns:
            chart_df['SMA50'] = chart_df['Close'].rolling(50, min_periods=1).mean()
        if ind.get('sma200') is not None and 'Close' in chart_df.columns:
            chart_df['SMA200'] = chart_df['Close'].rolling(200, min_periods=1).mean()

        last_date = chart_df.index[-1].strftime("%Y-%m-%d")
        st.caption(f"Data through: {last_date} (market close) • Hover for details")

        price_chart = create_price_chart(chart_df, metal_name, height=350)
        if price_chart:
            st.plotly_chart(price_chart, use_container_width=True, config={'displayModeBar': False})

# === COMEX INVENTORY HISTORY TABLE ===
st.markdown("#### 📦 COMEX Warehouse Inventory (Last 10 Days)")

inventory_table = get_inventory_history_table(days=10)
if not inventory_table.empty:
    # Style the table
    st.markdown("""
<style>
.inventory-table {
    background: rgba(30, 37, 48, 0.6);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 20px;
}
.inventory-table table {
    width: 100%;
    border-collapse: collapse;
}
.inventory-table th {
    background: rgba(255, 255, 255, 0.1);
    padding: 10px;
    text-align: right;
    font-weight: 600;
    color: #e0e0e0;
}
.inventory-table th:first-child {
    text-align: left;
}
.inventory-table td {
    padding: 8px 10px;
    text-align: right;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    font-size: 0.85rem;
}
.inventory-table td:first-child {
    text-align: left;
    color: #888;
}
.inventory-table tr:hover {
    background: rgba(255, 255, 255, 0.03);
}
</style>
""", unsafe_allow_html=True)

    # Rename index for display
    inventory_table.index.name = "Date"

    st.dataframe(
        inventory_table,
        use_container_width=True,
        height=400
    )
    st.caption("Values show total inventory with day-over-day % change in brackets. Units: Gold/Silver in troy oz, Copper in lbs, Platinum/Palladium in troy oz.")
else:
    st.info("COMEX inventory data not yet available. Data is collected daily at 10:30 PM ET.")

st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)

# === GOLD ACCORDION ===
gold_header = f"🥇 GOLD — {format_price(gold_price)} — {gold_emoji} {gold_verdict_text}"
if gold_change is not None:
    gold_header += f" — {gold_change:+.1f}% today"

with st.expander(gold_header, expanded=False):
    render_technical_tab(gold_ind, gold_cot, gold_term, "Gold")

    # CME Warehouse Inventory Section
    st.markdown("#### 📦 COMEX Warehouse Inventory")

    gold_inv = get_latest_inventory("gold")
    gold_inv_state = get_inventory_state("gold")

    if gold_inv:
        inv_g1, inv_g2, inv_g3 = st.columns(3)
        with inv_g1:
            st.metric(
                "Total Inventory",
                f"{gold_inv['total']:,} oz" if gold_inv.get('total') else "N/A"
            )
        with inv_g2:
            change_5d = gold_inv.get('change_5d_pct')
            if change_5d is not None:
                st.metric("5-Day Change", f"{change_5d:+.2f}%", delta_color="inverse")
            else:
                st.metric("5-Day Change", "N/A")
        with inv_g3:
            if gold_inv_state and gold_inv_state.get('state') != 'unknown':
                st.metric("Inventory State", f"{gold_inv_state['emoji']} {gold_inv_state['state'].upper()}")
            else:
                st.metric("Inventory State", "Calculating...")

        if gold_inv_state and gold_inv_state.get('interpretation'):
            st.caption(gold_inv_state['interpretation'])
    else:
        st.info("CME inventory data not yet available. Runs daily at 10:30 PM ET.")

    # Price vs Inventory Pressure Analysis
    st.markdown("#### ⚡ Price vs Inventory Pressure")

    if "error" not in gold_pressure_data:
        pres_g1, pres_g2, pres_g3 = st.columns(3)
        with pres_g1:
            st.metric(
                "Pressure State",
                f"{gold_pressure_data['state_emoji']} {gold_pressure_data['pressure_state']}"
            )
        with pres_g2:
            price_5d = gold_pressure_data.get('price_pct_5d')
            st.metric(
                "Price 5D",
                f"{price_5d:+.1f}%" if price_5d else "N/A",
                gold_pressure_data.get('price_direction', '')
            )
        with pres_g3:
            inv_5d = gold_pressure_data.get('inv_pct_5d')
            st.metric(
                "Inventory 5D",
                f"{inv_5d:+.1f}%" if inv_5d else "N/A",
                gold_pressure_data.get('inventory_direction', ''),
                delta_color="inverse"
            )

        st.markdown(f"**{gold_pressure_data['state_description']}**")
        st.caption(f"Action: {gold_pressure_data['state_action']}")

        # Show streak if available
        streak = gold_pressure_data.get('state_streak_days')
        if streak and streak > 1:
            st.caption(f"State persistence: {streak} consecutive days")

        # Show data status if limited
        if gold_pressure_data.get('data_status') == 'limited':
            days = gold_pressure_data.get('days_of_inventory_data', 0)
            st.info(f"Building history: {days}/10 days of inventory data collected. Full pressure analysis coming soon.")
    else:
        st.warning("Pressure analysis unavailable")

    # AI Analysis button inside accordion
    if st.button("🤖 Generate Gold AI Analysis", use_container_width=True, key="btn_gold_ai_accordion"):
        with st.spinner("Claude is analyzing gold markets..."):
            gold_analysis = generate_ai_summary(
                "Gold", gold_price,
                gold_ind if "error" not in gold_ind else {},
                gold_cot, macro_data, gold_term,
                gold_five if "error" not in gold_five else None
            )
            if gold_analysis:
                st.markdown(gold_analysis)
            else:
                st.warning("AI analysis unavailable. Add ANTHROPIC_API_KEY to Streamlit secrets.")

# === SILVER ACCORDION ===
silver_header = f"🥈 SILVER — {format_price(silver_price)} — {silver_emoji} {silver_verdict_text}"
if silver_change is not None:
    silver_header += f" — {silver_change:+.1f}% today"

with st.expander(silver_header, expanded=False):
    render_technical_tab(silver_ind, silver_cot, silver_term, "Silver")

    # CME Warehouse Inventory Section
    st.markdown("#### 📦 COMEX Warehouse Inventory")

    silver_inv = get_latest_inventory("silver")
    silver_inv_state = get_inventory_state("silver")

    if silver_inv:
        inv_s1, inv_s2, inv_s3 = st.columns(3)
        with inv_s1:
            st.metric(
                "Total Inventory",
                f"{silver_inv['total']:,} oz" if silver_inv.get('total') else "N/A"
            )
        with inv_s2:
            change_5d = silver_inv.get('change_5d_pct')
            if change_5d is not None:
                st.metric("5-Day Change", f"{change_5d:+.2f}%", delta_color="inverse")
            else:
                st.metric("5-Day Change", "N/A")
        with inv_s3:
            if silver_inv_state and silver_inv_state.get('state') != 'unknown':
                st.metric("Inventory State", f"{silver_inv_state['emoji']} {silver_inv_state['state'].upper()}")
            else:
                st.metric("Inventory State", "Calculating...")

        if silver_inv_state and silver_inv_state.get('interpretation'):
            st.caption(silver_inv_state['interpretation'])
    else:
        st.info("CME inventory data not yet available. Runs daily at 10:30 PM ET.")

    # Price vs Inventory Pressure Analysis
    st.markdown("#### ⚡ Price vs Inventory Pressure")

    if "error" not in silver_pressure_data:
        pres_s1, pres_s2, pres_s3 = st.columns(3)
        with pres_s1:
            st.metric(
                "Pressure State",
                f"{silver_pressure_data['state_emoji']} {silver_pressure_data['pressure_state']}"
            )
        with pres_s2:
            price_5d = silver_pressure_data.get('price_pct_5d')
            st.metric(
                "Price 5D",
                f"{price_5d:+.1f}%" if price_5d else "N/A",
                silver_pressure_data.get('price_direction', '')
            )
        with pres_s3:
            inv_5d = silver_pressure_data.get('inv_pct_5d')
            st.metric(
                "Inventory 5D",
                f"{inv_5d:+.1f}%" if inv_5d else "N/A",
                silver_pressure_data.get('inventory_direction', ''),
                delta_color="inverse"
            )

        st.markdown(f"**{silver_pressure_data['state_description']}**")
        st.caption(f"Action: {silver_pressure_data['state_action']}")

        # Show streak if available
        streak = silver_pressure_data.get('state_streak_days')
        if streak and streak > 1:
            st.caption(f"State persistence: {streak} consecutive days")

        # Show data status if limited
        if silver_pressure_data.get('data_status') == 'limited':
            days = silver_pressure_data.get('days_of_inventory_data', 0)
            st.info(f"Building history: {days}/10 days of inventory data collected. Full pressure analysis coming soon.")
    else:
        st.warning("Pressure analysis unavailable")

    # AI Analysis button inside accordion
    if st.button("🤖 Generate Silver AI Analysis", use_container_width=True, key="btn_silver_ai_accordion"):
        with st.spinner("Claude is analyzing silver markets..."):
            silver_analysis = generate_ai_summary(
                "Silver", silver_price,
                silver_ind if "error" not in silver_ind else {},
                silver_cot, macro_data, silver_term,
                silver_five if "error" not in silver_five else None
            )
            if silver_analysis:
                st.markdown(silver_analysis)
            else:
                st.warning("AI analysis unavailable. Add ANTHROPIC_API_KEY to Streamlit secrets.")

# === COPPER ACCORDION ===
copper_header = f"🔶 COPPER — {format_price(copper_price)}/lb — {copper_emoji} {copper_verdict_text}"
if copper_change is not None:
    copper_header += f" — {copper_change:+.1f}% today"

with st.expander(copper_header, expanded=False):
    render_technical_tab(copper_ind, copper_cot, copper_term, "Copper")

    # Copper-specific macro indicators
    st.markdown("#### 🔶 Copper Macro Drivers")
    with st.expander("ℹ️ Understanding Copper Drivers", expanded=False):
        st.markdown(COPPER_MACRO_GUIDE)

    if "error" not in copper_macro:
        copper_indicators = copper_macro.get("indicators", {})

        cm1, cm2, cm3 = st.columns(3)

        with cm1:
            china_pmi = copper_indicators.get("china_pmi", {})
            if "error" not in china_pmi and china_pmi.get("value") is not None:
                val = china_pmi.get("value", 0)
                impact = china_pmi.get("copper_impact", "neutral")
                regime = china_pmi.get("regime", "")
                st.metric("China PMI", f"{val:.1f}")
                st.caption(f"{regime}")
                st.caption(f"Copper: {signal_emoji(impact)} {impact}")
            else:
                st.metric("China PMI", "N/A")
                st.caption("Data unavailable")

        with cm2:
            us_pmi = copper_indicators.get("us_ism_pmi", {})
            if "error" not in us_pmi and us_pmi.get("value") is not None:
                val = us_pmi.get("value", 0)
                impact = us_pmi.get("copper_impact", "neutral")
                regime = us_pmi.get("regime", "")
                st.metric("US ISM PMI", f"{val:.1f}")
                st.caption(f"{regime}")
                st.caption(f"Copper: {signal_emoji(impact)} {impact}")
            else:
                st.metric("US ISM PMI", "N/A")
                st.caption("Data unavailable")

        with cm3:
            usd_cny = copper_indicators.get("usd_cny", {})
            if "error" not in usd_cny and usd_cny.get("value") is not None:
                val = usd_cny.get("value", 0)
                chg = usd_cny.get("change", 0)
                impact = usd_cny.get("copper_impact", "neutral")
                st.metric("USD/CNY", f"{val:.4f}", f"{chg:+.2f}%", delta_color="inverse")
                st.caption(f"Copper: {signal_emoji(impact)} {impact}")
            else:
                st.metric("USD/CNY", "N/A")
                st.caption("Data unavailable")
    else:
        st.warning("Copper macro data unavailable")

    # LME Inventory links
    st.markdown("#### 📦 LME Inventories (Check Manually)")
    with st.expander("ℹ️ Why Inventories Matter", expanded=False):
        st.markdown(COPPER_INVENTORY_GUIDE)

    st.info("""
**Pro Tip:** LME and SHFE aren't available via free APIs, but pros watch them closely:

- **[LME Copper Stocks](https://www.lme.com/en/metals/non-ferrous/lme-copper#Trading+day+summary)** - London Metal Exchange warehouse stocks
- **[SHFE Shanghai](https://www.shfe.com.cn/en/MarketData/DelWarehouse/)** - Shanghai Futures Exchange stocks

**Reading the signal:** Falling inventories = Physical tightness = BULLISH | Rising inventories = Oversupply = BEARISH
""")

    # CME Inventory (automated)
    st.markdown("#### 📦 COMEX Warehouse Inventory")

    copper_inv = get_latest_inventory("copper")
    copper_inv_state = get_inventory_state("copper")

    if copper_inv:
        inv_c1, inv_c2, inv_c3 = st.columns(3)
        with inv_c1:
            st.metric(
                "Total Inventory",
                f"{copper_inv['total']:,} lbs" if copper_inv.get('total') else "N/A"
            )
        with inv_c2:
            change_5d = copper_inv.get('change_5d_pct')
            if change_5d is not None:
                st.metric("5-Day Change", f"{change_5d:+.2f}%", delta_color="inverse")
            else:
                st.metric("5-Day Change", "N/A")
        with inv_c3:
            if copper_inv_state and copper_inv_state.get('state') != 'unknown':
                st.metric("Inventory State", f"{copper_inv_state['emoji']} {copper_inv_state['state'].upper()}")
            else:
                st.metric("Inventory State", "Calculating...")

        if copper_inv_state and copper_inv_state.get('interpretation'):
            st.caption(copper_inv_state['interpretation'])
    else:
        st.info("CME inventory data not yet available. Runs daily at 10:30 PM ET.")

    # Price vs Inventory Pressure Analysis
    st.markdown("#### ⚡ Price vs Inventory Pressure")

    copper_pressure = get_current_pressure("copper")

    if "error" not in copper_pressure:
        pres_c1, pres_c2, pres_c3 = st.columns(3)
        with pres_c1:
            st.metric(
                "Pressure State",
                f"{copper_pressure['state_emoji']} {copper_pressure['pressure_state']}"
            )
        with pres_c2:
            price_5d = copper_pressure.get('price_pct_5d')
            st.metric(
                "Price 5D",
                f"{price_5d:+.1f}%" if price_5d else "N/A",
                copper_pressure.get('price_direction', '')
            )
        with pres_c3:
            inv_5d = copper_pressure.get('inv_pct_5d')
            st.metric(
                "Inventory 5D",
                f"{inv_5d:+.1f}%" if inv_5d else "N/A",
                copper_pressure.get('inventory_direction', ''),
                delta_color="inverse"
            )

        st.markdown(f"**{copper_pressure['state_description']}**")
        st.caption(f"Action: {copper_pressure['state_action']}")

        # Show streak if available
        streak = copper_pressure.get('state_streak_days')
        if streak and streak > 1:
            st.caption(f"State persistence: {streak} consecutive days")

        # Show data status if limited
        if copper_pressure.get('data_status') == 'limited':
            days = copper_pressure.get('days_of_inventory_data', 0)
            st.info(f"Building history: {days}/10 days of inventory data collected. Full pressure analysis coming soon.")
    else:
        st.warning("Pressure analysis unavailable")

    # AI Analysis button inside accordion
    if st.button("🤖 Generate Copper AI Analysis", use_container_width=True, key="btn_copper_ai_accordion"):
        with st.spinner("Claude is analyzing copper markets..."):
            copper_analysis = generate_ai_summary(
                "Copper", copper_price,
                copper_ind if "error" not in copper_ind else {},
                copper_cot, copper_macro, copper_term,
                copper_five if "error" not in copper_five else None
            )
            if copper_analysis:
                st.markdown(copper_analysis)
            else:
                st.warning("AI analysis unavailable. Add ANTHROPIC_API_KEY to Streamlit secrets.")

# === PLATINUM ACCORDION ===
platinum_header = f"⚪ PLATINUM — {format_price(platinum_price)} — {platinum_emoji} {platinum_verdict_text}"
if platinum_change is not None:
    platinum_header += f" — {platinum_change:+.1f}% today"

with st.expander(platinum_header, expanded=False):
    render_technical_tab(platinum_ind, platinum_cot, platinum_term, "Platinum")

    # Platinum CME Inventory
    st.markdown("#### 📦 CME Warehouse Inventory")

    platinum_inv = get_latest_inventory("platinum")
    platinum_state = get_inventory_state("platinum")

    if platinum_inv:
        inv_c1, inv_c2, inv_c3 = st.columns(3)
        with inv_c1:
            st.metric(
                "Total Inventory",
                f"{platinum_inv['total']:,} oz" if platinum_inv.get('total') else "N/A"
            )
        with inv_c2:
            change_5d = platinum_inv.get('change_5d_pct')
            if change_5d is not None:
                st.metric("5-Day Change", f"{change_5d:+.2f}%", delta_color="inverse")
            else:
                st.metric("5-Day Change", "N/A")
        with inv_c3:
            if platinum_state and platinum_state.get('state') != 'unknown':
                st.metric("Inventory State", f"{platinum_state['emoji']} {platinum_state['state'].upper()}")
            else:
                st.metric("Inventory State", "Calculating...")

        if platinum_state and platinum_state.get('interpretation'):
            st.caption(platinum_state['interpretation'])
    else:
        st.info("CME inventory data not yet available. Runs daily at 10:30 PM ET.")

    # Pt/Pd Ratio Analysis
    st.markdown("#### ⚖️ Platinum/Palladium Ratio")

    ptpd_ratio = analyze_ptpd_ratio(platinum_price, palladium_price)

    if "error" not in ptpd_ratio:
        pt_signal, pt_color, pt_emoji = get_ratio_signal_text("platinum", ptpd_ratio)

        ratio_c1, ratio_c2, ratio_c3 = st.columns(3)
        with ratio_c1:
            st.metric("Pt/Pd Ratio", f"{ptpd_ratio['current_ratio']:.3f}")
        with ratio_c2:
            st.metric("5-Year Percentile", f"{ptpd_ratio['percentile']:.0f}%")
        with ratio_c3:
            st.metric("Platinum Relative Value", f"{pt_emoji} {pt_signal}")

        # Interpretation
        st.markdown(f"**{ptpd_ratio['interpretation']}**")

        if ptpd_ratio.get('trend_description'):
            trend_emoji = "📈" if ptpd_ratio['trend'] == "rising" else "📉" if ptpd_ratio['trend'] == "falling" else "➡️"
            st.caption(f"{trend_emoji} {ptpd_ratio['trend_description']}")

        # Chart in expander - Interactive Plotly
        with st.expander("📊 View Pt/Pd Ratio Chart (2 Years)", expanded=False):
            chart_data = ptpd_ratio.get('chart_data')
            if chart_data is not None and not chart_data.empty:
                # Create ratio chart with mean line
                ratio_fig = go.Figure()
                ratio_fig.add_trace(go.Scatter(
                    x=chart_data.index,
                    y=chart_data['Pt/Pd Ratio'],
                    mode='lines',
                    name='Ratio',
                    line=dict(color='#E5E4E2', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(229, 228, 226, 0.1)',
                    hovertemplate='%{x|%b %d, %Y}<br>Ratio: %{y:.3f}<extra></extra>'
                ))
                # Add mean line
                ratio_fig.add_hline(
                    y=ptpd_ratio['mean'],
                    line_dash="dash",
                    line_color="rgba(255,193,7,0.6)",
                    annotation_text=f"Mean: {ptpd_ratio['mean']:.3f}",
                    annotation_position="right"
                )
                ratio_fig.update_layout(
                    height=250,
                    margin=dict(l=0, r=60, t=10, b=0),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#888'),
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', side='right'),
                    showlegend=False,
                )
                st.plotly_chart(ratio_fig, use_container_width=True, config={'displayModeBar': False})
                st.caption(f"Mean: {ptpd_ratio['mean']:.3f} | Range: {ptpd_ratio['min']:.3f} - {ptpd_ratio['max']:.3f}")
    else:
        st.warning("Pt/Pd ratio data unavailable")

    # Price vs Inventory Pressure Analysis
    st.markdown("#### ⚡ Price vs Inventory Pressure")

    platinum_pressure = get_current_pressure("platinum")

    if "error" not in platinum_pressure:
        pres_c1, pres_c2, pres_c3 = st.columns(3)
        with pres_c1:
            st.metric(
                "Pressure State",
                f"{platinum_pressure['state_emoji']} {platinum_pressure['pressure_state']}"
            )
        with pres_c2:
            price_5d = platinum_pressure.get('price_pct_5d')
            st.metric(
                "Price 5D",
                f"{price_5d:+.1f}%" if price_5d else "N/A",
                platinum_pressure.get('price_direction', '')
            )
        with pres_c3:
            inv_5d = platinum_pressure.get('inv_pct_5d')
            st.metric(
                "Inventory 5D",
                f"{inv_5d:+.1f}%" if inv_5d else "N/A",
                platinum_pressure.get('inventory_direction', ''),
                delta_color="inverse"
            )

        st.markdown(f"**{platinum_pressure['state_description']}**")
        st.caption(f"Action: {platinum_pressure['state_action']}")

        streak = platinum_pressure.get('state_streak_days')
        if streak and streak > 1:
            st.caption(f"State persistence: {streak} consecutive days")

        if platinum_pressure.get('data_status') == 'limited':
            days = platinum_pressure.get('days_of_inventory_data', 0)
            st.info(f"Building history: {days}/10 days of inventory data collected. Full pressure analysis coming soon.")
    else:
        st.warning("Pressure analysis unavailable")

    # AI Analysis button inside accordion
    if st.button("🤖 Generate Platinum AI Analysis", use_container_width=True, key="btn_platinum_ai_accordion"):
        with st.spinner("Claude is analyzing platinum markets..."):
            platinum_analysis = generate_ai_summary(
                "Platinum", platinum_price,
                platinum_ind if "error" not in platinum_ind else {},
                platinum_cot, macro_data, platinum_term,
                None  # No 5-pillar for PGMs yet
            )
            if platinum_analysis:
                st.markdown(platinum_analysis)
            else:
                st.warning("AI analysis unavailable. Add ANTHROPIC_API_KEY to Streamlit secrets.")

# === PALLADIUM ACCORDION ===
palladium_header = f"⬜ PALLADIUM — {format_price(palladium_price)} — {palladium_emoji} {palladium_verdict_text}"
if palladium_change is not None:
    palladium_header += f" — {palladium_change:+.1f}% today"

with st.expander(palladium_header, expanded=False):
    render_technical_tab(palladium_ind, palladium_cot, palladium_term, "Palladium")

    # Palladium CME Inventory
    st.markdown("#### 📦 CME Warehouse Inventory")

    palladium_inv = get_latest_inventory("palladium")
    palladium_state = get_inventory_state("palladium")

    if palladium_inv:
        inv_c1, inv_c2, inv_c3 = st.columns(3)
        with inv_c1:
            st.metric(
                "Total Inventory",
                f"{palladium_inv['total']:,} oz" if palladium_inv.get('total') else "N/A"
            )
        with inv_c2:
            change_5d = palladium_inv.get('change_5d_pct')
            if change_5d is not None:
                st.metric("5-Day Change", f"{change_5d:+.2f}%", delta_color="inverse")
            else:
                st.metric("5-Day Change", "N/A")
        with inv_c3:
            if palladium_state and palladium_state.get('state') != 'unknown':
                st.metric("Inventory State", f"{palladium_state['emoji']} {palladium_state['state'].upper()}")
            else:
                st.metric("Inventory State", "Calculating...")

        if palladium_state and palladium_state.get('interpretation'):
            st.caption(palladium_state['interpretation'])
    else:
        st.info("CME inventory data not yet available. Runs daily at 10:30 PM ET.")

    # Pt/Pd Ratio Analysis (from Palladium perspective)
    st.markdown("#### ⚖️ Platinum/Palladium Ratio")

    # Reuse the ratio data if already computed, otherwise compute
    if 'ptpd_ratio' not in dir() or "error" in ptpd_ratio:
        ptpd_ratio = analyze_ptpd_ratio(platinum_price, palladium_price)

    if "error" not in ptpd_ratio:
        pd_signal, pd_color, pd_emoji = get_ratio_signal_text("palladium", ptpd_ratio)

        ratio_c1, ratio_c2, ratio_c3 = st.columns(3)
        with ratio_c1:
            st.metric("Pt/Pd Ratio", f"{ptpd_ratio['current_ratio']:.3f}")
        with ratio_c2:
            st.metric("5-Year Percentile", f"{ptpd_ratio['percentile']:.0f}%")
        with ratio_c3:
            st.metric("Palladium Relative Value", f"{pd_emoji} {pd_signal}")

        # Interpretation (inverted for palladium perspective)
        if ptpd_ratio['palladium_signal'] == "cheap":
            pd_interpretation = "Palladium historically cheap vs Platinum - potential value opportunity"
        elif ptpd_ratio['palladium_signal'] == "expensive":
            pd_interpretation = "Palladium historically expensive vs Platinum - elevated valuation"
        else:
            pd_interpretation = "Ratio near historical average - no strong relative value signal"

        st.markdown(f"**{pd_interpretation}**")

        if ptpd_ratio.get('trend_description'):
            # Invert trend description for palladium
            if ptpd_ratio['trend'] == "rising":
                pd_trend = "Palladium weakening vs Platinum"
            elif ptpd_ratio['trend'] == "falling":
                pd_trend = "Palladium strengthening vs Platinum"
            else:
                pd_trend = "Ratio stable over past 20 days"
            trend_emoji = "📉" if ptpd_ratio['trend'] == "rising" else "📈" if ptpd_ratio['trend'] == "falling" else "➡️"
            st.caption(f"{trend_emoji} {pd_trend}")

        # Chart in expander - Interactive Plotly
        with st.expander("📊 View Pt/Pd Ratio Chart (2 Years)", expanded=False):
            chart_data = ptpd_ratio.get('chart_data')
            if chart_data is not None and not chart_data.empty:
                # Create ratio chart with mean line (inverted perspective for palladium)
                ratio_fig = go.Figure()
                ratio_fig.add_trace(go.Scatter(
                    x=chart_data.index,
                    y=chart_data['Pt/Pd Ratio'],
                    mode='lines',
                    name='Ratio',
                    line=dict(color='#CED0DD', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(206, 208, 221, 0.1)',
                    hovertemplate='%{x|%b %d, %Y}<br>Ratio: %{y:.3f}<extra></extra>'
                ))
                # Add mean line
                ratio_fig.add_hline(
                    y=ptpd_ratio['mean'],
                    line_dash="dash",
                    line_color="rgba(255,193,7,0.6)",
                    annotation_text=f"Mean: {ptpd_ratio['mean']:.3f}",
                    annotation_position="right"
                )
                ratio_fig.update_layout(
                    height=250,
                    margin=dict(l=0, r=60, t=10, b=0),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#888'),
                    xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', side='right'),
                    showlegend=False,
                )
                st.plotly_chart(ratio_fig, use_container_width=True, config={'displayModeBar': False})
                st.caption(f"Mean: {ptpd_ratio['mean']:.3f} | Range: {ptpd_ratio['min']:.3f} - {ptpd_ratio['max']:.3f}")
    else:
        st.warning("Pt/Pd ratio data unavailable")

    # Price vs Inventory Pressure Analysis
    st.markdown("#### ⚡ Price vs Inventory Pressure")

    palladium_pressure = get_current_pressure("palladium")

    if "error" not in palladium_pressure:
        pres_c1, pres_c2, pres_c3 = st.columns(3)
        with pres_c1:
            st.metric(
                "Pressure State",
                f"{palladium_pressure['state_emoji']} {palladium_pressure['pressure_state']}"
            )
        with pres_c2:
            price_5d = palladium_pressure.get('price_pct_5d')
            st.metric(
                "Price 5D",
                f"{price_5d:+.1f}%" if price_5d else "N/A",
                palladium_pressure.get('price_direction', '')
            )
        with pres_c3:
            inv_5d = palladium_pressure.get('inv_pct_5d')
            st.metric(
                "Inventory 5D",
                f"{inv_5d:+.1f}%" if inv_5d else "N/A",
                palladium_pressure.get('inventory_direction', ''),
                delta_color="inverse"
            )

        st.markdown(f"**{palladium_pressure['state_description']}**")
        st.caption(f"Action: {palladium_pressure['state_action']}")

        streak = palladium_pressure.get('state_streak_days')
        if streak and streak > 1:
            st.caption(f"State persistence: {streak} consecutive days")

        if palladium_pressure.get('data_status') == 'limited':
            days = palladium_pressure.get('days_of_inventory_data', 0)
            st.info(f"Building history: {days}/10 days of inventory data collected. Full pressure analysis coming soon.")
    else:
        st.warning("Pressure analysis unavailable")

    # AI Analysis button inside accordion
    if st.button("🤖 Generate Palladium AI Analysis", use_container_width=True, key="btn_palladium_ai_accordion"):
        with st.spinner("Claude is analyzing palladium markets..."):
            palladium_analysis = generate_ai_summary(
                "Palladium", palladium_price,
                palladium_ind if "error" not in palladium_ind else {},
                palladium_cot, macro_data, palladium_term,
                None  # No 5-pillar for PGMs yet
            )
            if palladium_analysis:
                st.markdown(palladium_analysis)
            else:
                st.warning("AI analysis unavailable. Add ANTHROPIC_API_KEY to Streamlit secrets.")

# === FOOTER ===
st.markdown('<div class="custom-divider"></div>', unsafe_allow_html=True)
st.markdown(f'<p class="timestamp">Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | Data may be delayed</p>', unsafe_allow_html=True)

with st.expander("🔧 Debug: Raw API Responses"):
    d1, d2, d3 = st.columns(3)
    with d1:
        st.write("**Gold Raw:**")
        st.code(str(gold_raw)[:500] if gold_raw else "No data")
    with d2:
        st.write("**Silver Raw:**")
        st.code(str(silver_raw)[:500] if silver_raw else "No data")
    with d3:
        st.write("**Copper Raw:**")
        st.code(str(copper_raw)[:500] if copper_raw else "No data")
