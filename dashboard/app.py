"""
SignalStack: Universal Attention & Crypto Intelligence Terminal.

Three modes (sidebar):
  1. Crypto Asset       — full stack (BTC/ETH/SOL/XRP/DOGE)
  2. Keyword Search     — Google Trends + Google News for ANY term
  3. Compare Keywords   — side-by-side Trends + News for up to 5 terms

Run from project root:
    python -m streamlit run dashboard/app.py
"""

import logging
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_sources.binance_client import get_funding_rates  # noqa: E402
from data_sources.google_trends import VALID_TIMEFRAMES  # noqa: E402
from engine.keyword_engine import compare_keywords, compute_keyword_signals  # noqa: E402
from engine.signal_engine import compute_signals  # noqa: E402
from utils.cache import cache  # noqa: E402
from utils.config import (  # noqa: E402
    COLOR_BEARISH,
    COLOR_BULLISH,
    COLOR_CHART_BG,
    COLOR_NEUTRAL,
    STREAMLIT_LAYOUT,
    STREAMLIT_PAGE_ICON,
    STREAMLIT_PAGE_TITLE,
    SUPPORTED_ASSETS,
)

st.set_page_config(
    page_title=STREAMLIT_PAGE_TITLE,
    page_icon=STREAMLIT_PAGE_ICON,
    layout=STREAMLIT_LAYOUT,
    initial_sidebar_state="expanded",
)

logging.basicConfig(level=logging.INFO)

st.markdown(
    """
<style>
    .signal-card {
        padding: 16px 20px;
        border-radius: 8px;
        margin: 12px 0;
    }
    .signal-bullish { background: #1a3a2a; border-left: 4px solid #00D084; }
    .signal-bearish { background: #3a1a1a; border-left: 4px solid #F44033; }
    .signal-neutral { background: #2a2a2a; border-left: 4px solid #9CA3AF; }
    .preset-chip {
        display: inline-block;
        padding: 4px 10px;
        margin: 2px;
        background: #1a1a1a;
        border-radius: 12px;
        font-size: 0.85em;
    }
</style>
""",
    unsafe_allow_html=True,
)


PRESET_KEYWORDS = [
    "AI", "ChatGPT", "OpenAI", "Claude AI",
    "Bitcoin", "Ethereum", "Solana",
    "Tesla", "Nvidia", "Apple",
    "Trump", "Elon Musk", "Taylor Swift",
    "Web3", "DeFi", "NFT",
    "Recession", "Inflation", "Fed rate cut",
]


# ============================================================================
# UTILITIES
# ============================================================================

def format_currency(value: float) -> str:
    sign = "-" if value < 0 else ""
    v = abs(value)
    if v >= 1_000_000_000:
        return f"{sign}${v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{sign}${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{sign}${v/1_000:.2f}K"
    return f"{sign}${v:.0f}"


def gauge_chart(value: float, title: str, max_value: float = 100) -> go.Figure:
    color = (
        COLOR_BULLISH if value > max_value * 0.65
        else COLOR_BEARISH if value < max_value * 0.35
        else COLOR_NEUTRAL
    )
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": title},
            gauge={
                "axis": {"range": [0, max_value]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0, max_value * 0.3], "color": "#3a1a1a"},
                    {"range": [max_value * 0.3, max_value * 0.7], "color": "#2a2a2a"},
                    {"range": [max_value * 0.7, max_value], "color": "#1a3a2a"},
                ],
            },
        )
    )
    fig.update_layout(
        height=300,
        margin=dict(l=40, r=40, t=50, b=20),
        paper_bgcolor=COLOR_CHART_BG,
        font=dict(color="white"),
    )
    return fig


def render_signal_card(signal: dict) -> None:
    bias = signal.get("bias", "NEUTRAL")
    if bias == "BULLISH":
        emoji, css = "[B]", "signal-bullish"
    elif bias == "BEARISH":
        emoji, css = "[X]", "signal-bearish"
    else:
        emoji, css = "[~]", "signal-neutral"

    st.markdown(f'<div class="signal-card {css}">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 5, 1])
    with col1:
        st.markdown(f"### {emoji}")
    with col2:
        title = signal["pattern_name"].replace("_", " ").title()
        st.markdown(f"**{title}** — {bias}")
        st.write(signal["explanation"])
        st.caption(f"Action: {signal['suggested_action']}")
    with col3:
        st.metric("Confidence", f"{int(signal['confidence']*100)}%")
    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================================
# CRYPTO ASSET MODE
# ============================================================================

def render_crypto_mode(asset: str, show_debug: bool) -> None:
    st.title(f"SignalStack: {asset} Intelligence Terminal")

    try:
        signals = compute_signals(asset)
    except Exception as e:
        st.error(f"Error computing signals: {e}")
        return

    st.subheader("Real-Time Snapshot")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric(
            "Flow Score",
            f"{signals['flow_score']:.0f}",
            delta=f"{signals['flow_score_delta_24h']:+.1f}",
        )
    with c2:
        st.metric(
            "ETF Flow (latest)",
            format_currency(signals["layers"]["capital"]["etf_flow_latest_usd"]),
        )
    with c3:
        rate = signals["layers"]["capital"]["funding_rate_current"]
        st.metric("Funding Rate", f"{rate*100:.4f}%")
    with c4:
        st.metric("Risk Level", signals["risk_level"])
    with c5:
        st.metric("Data Quality", f"{signals['confidence']*100:.0f}%")

    st.divider()
    st.subheader("Attention Layer (Retail Narrative)")
    attention = signals["layers"]["attention"]
    a1, a2, a3 = st.columns(3)
    with a1:
        st.metric("Google Trends Spike", f"{attention['google_trends_spike']:.0f}/100")
    with a2:
        rank = attention["coingecko_trending_rank"]
        st.metric("CoinGecko Trending", f"#{rank}" if rank else "Not in Top 7")
    with a3:
        st.metric("News Velocity", f"{attention['news_velocity_score']:.0f}/100")
    st.plotly_chart(gauge_chart(attention["narrative_intensity"], "Narrative Intensity"),
                    use_container_width=True)

    st.divider()
    st.subheader("Capital Flow & Positioning")
    capital = signals["layers"]["capital"]
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("ETF Flow Direction", f"{capital['etf_flow_direction_score']:.0f}/100")
    with k2:
        st.metric("Funding Extremity", f"{capital['funding_extremity_score']:.0f}/100")
    with k3:
        st.metric("Funding Percentile", f"{capital['funding_rate_percentile']:.0f}th")
    with k4:
        st.metric("OI Trend", capital["open_interest_trend"])

    funding_resp = get_funding_rates(asset)
    funding_df = funding_resp.get("raw")
    if isinstance(funding_df, pd.DataFrame) and not funding_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=funding_df["timestamp"],
            y=funding_df["funding_rate"] * 100,
            mode="lines",
            line=dict(color=COLOR_BULLISH, width=2),
            name="Funding Rate (%)",
        ))
        fig.update_layout(
            title="Funding Rate History (~30 days)",
            paper_bgcolor=COLOR_CHART_BG, plot_bgcolor=COLOR_CHART_BG,
            font=dict(color="white"), height=300,
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Momentum & Price Action")
    momentum = signals["layers"]["momentum"]
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Volume Momentum", f"{momentum['volume_momentum_score']:.0f}/100")
    with m2:
        st.metric("24h Price Change", f"{momentum['price_change_24h']:+.2f}%")
    with m3:
        st.metric("24h Volatility", f"{momentum['volatility_24h']:.2f}%")

    st.divider()
    st.subheader("Composite Flow Score")
    st.plotly_chart(gauge_chart(signals["flow_score"], "Flow Score"), use_container_width=True)

    breakdown = signals["component_breakdown"]
    fig = go.Figure(data=[go.Bar(
        y=["Attention", "Capital", "Momentum"],
        x=[breakdown["attention"], breakdown["capital"], breakdown["momentum"]],
        orientation="h",
        marker=dict(color=[COLOR_BULLISH, COLOR_NEUTRAL, COLOR_BEARISH]),
    )])
    fig.update_layout(
        xaxis_title="Score (0-100)", height=250,
        paper_bgcolor=COLOR_CHART_BG, plot_bgcolor=COLOR_CHART_BG,
        font=dict(color="white"),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Divergence Patterns & Signals")
    if signals["divergences"]:
        for sig in signals["divergences"]:
            render_signal_card(sig)
    else:
        st.info("No divergence patterns detected. Signals are aligned.")

    if show_debug:
        st.divider()
        with st.expander("Data Quality"):
            dq = signals["data_quality"]
            st.write(f"**Available Sources:** {', '.join(dq['sources_available']) or 'None'}")
            if dq["sources_failed"]:
                st.warning(f"**Failed Sources:** {', '.join(dq['sources_failed'])}")
        with st.expander("Raw Signal JSON"):
            st.json(signals, expanded=False)
        with st.expander("Cache Info"):
            st.json(cache.get_cache_info())


# ============================================================================
# KEYWORD SEARCH MODE
# ============================================================================

def render_keyword_mode(keyword: str, timeframe: str, show_debug: bool) -> None:
    st.title(f"Keyword Search: {keyword!r}")
    st.caption(f"Timeframe: `{timeframe}` — Google Trends + Google News RSS (works for ANY term)")

    with st.spinner(f"Pulling live data for '{keyword}'..."):
        try:
            data = compute_keyword_signals(keyword, timeframe=timeframe)
        except Exception as e:
            st.error(f"Error: {e}")
            return

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Attention Score", f"{data['attention_score']:.0f}/100",
                  delta=data["signal_strength"])
    with c2:
        velocity = data["trends"]["trend_velocity"]
        st.metric("Trend Velocity", f"{velocity:+.2f}",
                  delta="Rising" if velocity > 0 else "Falling")
    with c3:
        st.metric("News Headlines (24h)", data["news"]["headlines_24h"])
    with c4:
        st.metric("Narrative State", data["narrative_state"])

    st.divider()

    # Trends chart
    trends_df = data["trends"]["raw"]
    if isinstance(trends_df, pd.DataFrame) and not trends_df.empty:
        st.subheader(f"Google Trends interest over time — '{keyword}'")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=trends_df["date"],
            y=trends_df["trend_value"],
            mode="lines",
            fill="tozeroy",
            line=dict(color=COLOR_BULLISH, width=2),
            name=keyword,
        ))
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Interest (0-100)",
            paper_bgcolor=COLOR_CHART_BG, plot_bgcolor=COLOR_CHART_BG,
            font=dict(color="white"), height=380, hovermode="x unified",
        )
        st.plotly_chart(fig, use_container_width=True)

        t1, t2, t3, t4 = st.columns(4)
        with t1:
            st.metric("Current Interest", f"{data['trends']['current_value']:.0f}/100")
        with t2:
            st.metric("Period Peak", f"{data['trends']['peak_value']:.0f}/100")
        with t3:
            st.metric("Period Average", f"{data['trends']['average_value']:.1f}")
        with t4:
            st.metric("Spike Score", f"{data['trends']['trend_spike_score']:.0f}/100")
    else:
        st.warning(f"Google Trends returned no data for '{keyword}'. Try a more common term or different timeframe.")
        if data["trends"].get("error"):
            st.caption(f"Error: {data['trends']['error']}")

    st.divider()
    st.plotly_chart(gauge_chart(data["attention_score"], "Composite Attention Score"),
                    use_container_width=True)

    # News mentions over time (always works since Google News RSS is reliable)
    news_df = data["news"]["raw"]
    if isinstance(news_df, pd.DataFrame) and not news_df.empty:
        st.divider()
        st.subheader(f"News mentions over time — '{keyword}'")
        nd = news_df.copy()
        nd["timestamp"] = pd.to_datetime(nd["timestamp"], utc=True)
        # Bucket: hourly if all within 48h, else daily
        span_hours = (nd["timestamp"].max() - nd["timestamp"].min()).total_seconds() / 3600
        freq = "h" if span_hours <= 48 else "D"
        bucket_label = "hour" if freq == "h" else "day"
        bucketed = (
            nd.set_index("timestamp")
              .resample(freq)
              .size()
              .reset_index(name="headline_count")
        )
        fig_news = go.Figure()
        fig_news.add_trace(go.Bar(
            x=bucketed["timestamp"],
            y=bucketed["headline_count"],
            marker=dict(color=COLOR_BULLISH),
            name=f"Headlines per {bucket_label}",
        ))
        fig_news.update_layout(
            xaxis_title=f"Time ({bucket_label} buckets)",
            yaxis_title="Headline count",
            paper_bgcolor=COLOR_CHART_BG, plot_bgcolor=COLOR_CHART_BG,
            font=dict(color="white"), height=300, hovermode="x",
        )
        st.plotly_chart(fig_news, use_container_width=True)

    # News
    st.divider()
    st.subheader(f"News spikes — '{keyword}' (Google News RSS)")
    n1, n2, n3, n4 = st.columns(4)
    with n1:
        st.metric("Headlines (24h)", data["news"]["headlines_24h"])
    with n2:
        st.metric("Daily avg (7d)", f"{data['news']['headlines_7d_avg']:.1f}")
    with n3:
        st.metric("News Velocity", f"{data['news']['news_velocity_score']:.0f}/100")
    with n4:
        st.metric("Spike Detected", "YES" if data["news"]["news_spike_detected"] else "no")

    if isinstance(news_df, pd.DataFrame) and not news_df.empty:
        with st.expander(f"Latest headlines ({len(news_df)} found)", expanded=True):
            display_df = news_df.head(20).copy()
            display_df["timestamp"] = display_df["timestamp"].dt.strftime("%Y-%m-%d %H:%M UTC")
            for _, row in display_df.iterrows():
                st.markdown(
                    f"- **[{row['headline']}]({row['link']})**  \n"
                    f"  `{row['source']}` · {row['timestamp']}"
                )

        if data["news"]["top_sources"]:
            with st.expander("Top news sources"):
                src_df = pd.DataFrame(
                    list(data["news"]["top_sources"].items()),
                    columns=["source", "headlines"],
                )
                st.dataframe(src_df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No news headlines found for '{keyword}' in Google News RSS.")
        if data["news"].get("error"):
            st.caption(f"Error: {data['news']['error']}")

    # Related queries
    if data["related"]["top"] or data["related"]["rising"]:
        st.divider()
        st.subheader("Related Google searches")
        rc1, rc2 = st.columns(2)
        with rc1:
            st.markdown("**Top related**")
            if data["related"]["top"]:
                st.dataframe(pd.DataFrame(data["related"]["top"]),
                             use_container_width=True, hide_index=True)
            else:
                st.caption("None")
        with rc2:
            st.markdown("**Rising related**")
            if data["related"]["rising"]:
                st.dataframe(pd.DataFrame(data["related"]["rising"]),
                             use_container_width=True, hide_index=True)
            else:
                st.caption("None")

    if show_debug:
        st.divider()
        with st.expander("Data Quality"):
            dq = data["data_quality"]
            st.write(f"**Available Sources:** {', '.join(dq['sources_available']) or 'None'}")
            if dq["sources_failed"]:
                st.warning(f"**Failed Sources:** {', '.join(dq['sources_failed'])}")
        with st.expander("Raw payload"):
            payload = {k: v for k, v in data.items() if k not in ("trends", "news")}
            payload["trends_summary"] = {k: v for k, v in data["trends"].items() if k != "raw"}
            payload["news_summary"] = {k: v for k, v in data["news"].items() if k != "raw"}
            st.json(payload, expanded=False)


# ============================================================================
# COMPARE KEYWORDS MODE
# ============================================================================

def render_compare_mode(keywords: list, timeframe: str, show_debug: bool) -> None:
    st.title(f"Compare: {' vs '.join(keywords)}")
    st.caption(f"Timeframe: `{timeframe}` — up to 5 keywords on Google Trends + per-keyword news velocity")

    with st.spinner("Pulling live comparison data..."):
        try:
            data = compare_keywords(keywords, timeframe=timeframe)
        except Exception as e:
            st.error(f"Error: {e}")
            return

    if data.get("trends_error"):
        st.error(f"Google Trends error: {data['trends_error']}")

    trends_df = data.get("trends_raw")
    if isinstance(trends_df, pd.DataFrame) and not trends_df.empty:
        st.subheader("Side-by-side interest over time")
        plot_cols = [c for c in keywords if c in trends_df.columns]
        if plot_cols:
            fig = go.Figure()
            palette = px.colors.qualitative.Set2
            for i, kw in enumerate(plot_cols):
                fig.add_trace(go.Scatter(
                    x=trends_df["date"],
                    y=trends_df[kw],
                    mode="lines",
                    name=kw,
                    line=dict(color=palette[i % len(palette)], width=2),
                ))
            fig.update_layout(
                xaxis_title="Date", yaxis_title="Interest (0-100)",
                paper_bgcolor=COLOR_CHART_BG, plot_bgcolor=COLOR_CHART_BG,
                font=dict(color="white"), height=420, hovermode="x unified",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No trend data returned. Some keywords may be too niche or rate-limited.")

    if data.get("winner"):
        st.success(f"Current winner by Google Trends interest: **{data['winner']}**")

    st.divider()
    st.subheader("Per-keyword breakdown")

    cols = st.columns(len(keywords))
    for col, kw in zip(cols, keywords):
        with col:
            st.markdown(f"### {kw}")
            per = data["per_keyword"].get(kw, {})
            trends = per.get("trends", {})
            st.metric("Current", f"{trends.get('current', 0):.0f}/100")
            st.metric("Peak", f"{trends.get('peak', 0):.0f}/100")
            st.metric("Spike Score", f"{trends.get('spike_score', 0):.0f}/100")
            st.metric("News (24h)", per.get("headlines_24h", 0))
            st.metric("News Velocity", f"{per.get('news_velocity_score', 0):.0f}/100")

    if show_debug:
        st.divider()
        with st.expander("Raw comparison payload"):
            payload = {k: v for k, v in data.items() if k != "trends_raw"}
            st.json(payload, expanded=False)


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    with st.sidebar:
        st.title("SignalStack")
        st.caption("Universal attention + crypto intelligence")

        mode = st.radio(
            "Mode",
            ["Keyword Search", "Crypto Asset", "Compare Keywords"],
            index=0,
            help="Pick what you want to analyze.",
        )

        st.divider()

        if mode == "Crypto Asset":
            asset = st.selectbox("Asset", SUPPORTED_ASSETS, index=0)
            keyword = None
            keywords = []
            timeframe = "now 7-d"
            if st.button("Refresh Data"):
                cache.delete(f"signals_{asset}")
                st.rerun()

        elif mode == "Keyword Search":
            keyword = st.text_input(
                "Search any keyword",
                value="AI",
                placeholder="e.g. AI, ChatGPT, Tesla, Taylor Swift, Bitcoin",
            ).strip()
            timeframe = st.selectbox(
                "Timeframe",
                VALID_TIMEFRAMES,
                index=VALID_TIMEFRAMES.index("now 7-d"),
                help="How far back to pull Google Trends data",
            )
            asset = None
            keywords = []
            st.markdown("**Quick presets:**")
            preset = st.selectbox(
                "Pick a suggestion",
                ["—"] + PRESET_KEYWORDS,
                label_visibility="collapsed",
            )
            if preset != "—":
                keyword = preset
            if st.button("Refresh Data"):
                cache.delete(f"keyword_signals_{keyword}_{timeframe}".replace(" ", "_"))
                st.rerun()

        else:  # Compare Keywords
            kw_input = st.text_area(
                "Keywords (comma-separated, max 5)",
                value="AI, ChatGPT, Bitcoin",
                height=80,
                help="Compare up to 5 terms on the same Google Trends scale.",
            )
            keywords = [k.strip() for k in kw_input.split(",") if k.strip()][:5]
            timeframe = st.selectbox(
                "Timeframe",
                VALID_TIMEFRAMES,
                index=VALID_TIMEFRAMES.index("now 7-d"),
            )
            asset = None
            keyword = None
            if st.button("Refresh Data"):
                cache_key = f"keyword_compare_{'_'.join(keywords)}_{timeframe}".replace(" ", "_")
                cache.delete(cache_key)
                st.rerun()

        st.divider()
        show_debug = st.checkbox("Show debug info")
        st.divider()
        st.caption("SignalStack v1.1 — keyword search added")

    # Route
    if mode == "Crypto Asset":
        render_crypto_mode(asset, show_debug)
    elif mode == "Keyword Search":
        if not keyword:
            st.info("Type a keyword in the sidebar to begin.")
            return
        render_keyword_mode(keyword, timeframe, show_debug)
    else:
        if not keywords:
            st.info("Enter at least one keyword in the sidebar.")
            return
        render_compare_mode(keywords, timeframe, show_debug)

    st.divider()
    st.markdown(
        "**Disclaimer:** Educational use only. Not financial advice. "
        "Live data from Google Trends, Google News, Binance, CoinGecko, Farside, CryptoPanic. "
        "All free public APIs."
    )


if __name__ == "__main__":
    main()
