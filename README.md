# SignalStack: Free Crypto Intelligence Terminal

A zero-cost production-grade cryptocurrency intelligence dashboard that aggregates global attention, capital flows, and market structure into actionable signals.

---

## What Is SignalStack?

SignalStack answers one critical question:

> When retail attention, institutional capital flows, and market positioning are aligned, which direction are they pushing?

It is a **data engineering + signal design** project that:

- Ingests free public APIs (Binance, CoinGecko, Farside, pytrends, CryptoPanic)
- Normalizes and scores attention, capital, and momentum on a 0-100 scale
- Detects divergence patterns (hype without conviction, smart money accumulation, trapped longs, momentum breakout, conflicting signals)
- Outputs interpretable signals with confidence scoring
- Deploys zero-cost to Streamlit Community Cloud

**Designed for:** Web3 / crypto employers (Binance, OKX, trading firms, DeFi protocols) hiring junior data / quant engineers.

---

## Architecture

```
+---------------------------------------------------+
|         DATA COLLECTION LAYER                      |
+---------------------------------------------------+
|  CoinGecko API   Binance API   Farside   pytrends  |
|  (Price, Trends) (Funding, OI) (Flows)   (Trends)  |
+---------------+-----------------------------------+
                |
                v
+---------------------------------------------------+
|  NORMALIZATION & CACHING LAYER                     |
|  (Handle failures gracefully, file-based TTL)      |
+---------------+-----------------------------------+
                |
                v
+---------------------------------------------------+
|      SIGNAL COMPUTATION ENGINE                     |
|  +--------------+  +-----------------------+       |
|  | Flow Scorer  |  | Divergence Detector   |       |
|  | (Composite)  |  | (Pattern matching)    |       |
|  +--------------+  +-----------------------+       |
+---------------+-----------------------------------+
                |
                v
+---------------------------------------------------+
|    STREAMLIT DASHBOARD                             |
|  (Real-time metrics, charts, signals)              |
+---------------------------------------------------+
```

### Three Layers

**Layer 1: Attention Engine** (Demand-side)
- Google Trends spike detection (`pytrends`)
- CoinGecko trending rank
- News velocity via CryptoPanic

**Layer 2: Capital Flow Engine** (Money side)
- ETF inflows via Farside Investors scraping
- Funding rates from Binance (leverage positioning)
- Open interest trend proxy from kline volume changes

**Layer 3: Opportunity / Alpha Engine** (Signals)
- Composite **Flow Score** (0-100): weighted aggregation
- **Divergence patterns**: smart money accumulation, hype without conviction, trapped longs, momentum breakouts, conflicting signals
- **Risk labeling**: CALM / ELEVATED / EXTREME

---

## Data Sources

| Source | Type | Free | Rate Limit | Module |
|---|---|---|---|---|
| **Google Trends** | API | Yes | ~1200/min | `data_sources/google_trends.py` |
| **CoinGecko** | API | Yes | 10-50/min | `data_sources/coingecko_client.py` |
| **Binance Futures** | API | Yes (public) | 1200/min | `data_sources/binance_client.py` |
| **Farside Investors** | HTML scrape | Yes | Daily | `data_sources/etf_flows_scraper.py` |
| **CryptoPanic** | API (DEMO) | Yes | Free tier | `data_sources/news_spike.py` |

All endpoints are completely free with no credit card required.

---

## Key Signals (Divergence Patterns)

### 1. Smart Money Accumulation
- **Rule:** ETF inflow HIGH + Retail attention LOW
- **Bias:** BULLISH
- **Interpretation:** Institutions quietly loading while retail sleeps. Often precedes 2-4 week rallies.

### 2. Hype Without Conviction
- **Rule:** Retail attention HIGH + ETF inflow LOW
- **Bias:** BEARISH
- **Interpretation:** FOMO without institutional backing. Risk of pullback.

### 3. Trapped Longs
- **Rule:** Funding rates EXTREME (90th+ percentile) + Price FLAT
- **Bias:** BEARISH
- **Interpretation:** Overcrowded leveraged longs. Liquidation cascade risk.

### 4. Momentum Breakout
- **Rule:** All signals aligned > 70 + Funding rates NOT extreme
- **Bias:** BULLISH
- **Interpretation:** Clean setup with room to run. Sustained move likely.

### 5. Conflicting Signals
- **Rule:** ETF flow vs retail attention diverge > 40 points
- **Bias:** NEUTRAL
- **Interpretation:** Institutions / retail not aligned. Elevated volatility, unclear direction.

---

## Flow Score Formula

```python
flow_score = (
    google_trends_spike       * 0.15
    + coingecko_trending_score * 0.15
    + etf_flow_direction_score * 0.25
    + funding_extremity_score  * 0.20
    + volume_momentum_score    * 0.25
) * confidence_discount

# All inputs normalized to 0-100
# confidence_discount in [0.5, 1.0] reflects how many sources returned data
```

Weights live in `utils/config.py` and are configurable.

---

## Caching Strategy

- **TTL per endpoint:** 15m (price/funding) up to 24h (ETF flows / trends)
- **Survives Streamlit reruns:** file-based cache in `~/.signalstack_cache/`
- **Auto-pickle for DataFrames:** JSON for plain dicts, pickle when payload contains pandas DataFrames
- **Fallback:** if a fresh fetch fails, return last cached value with an `error` label set

---

## Error Handling

- **Timeout:** return cached data with freshness label
- **Parse error:** log, continue with remaining sources
- **Missing data:** reduce confidence score proportionally
- **No hard crashes:** every data source returns a result dict (with `error` populated on failure)

---

## Repository Structure

```
SignalStack/
├── data_sources/
│   ├── __init__.py
│   ├── coingecko_client.py       # Price, trending, market chart
│   ├── binance_client.py         # Funding rates, klines, OI proxy
│   ├── etf_flows_scraper.py      # Farside HTML scraping
│   ├── google_trends.py          # pytrends wrapper
│   └── news_spike.py             # CryptoPanic news velocity
│
├── engine/
│   ├── __init__.py
│   ├── flow_scorer.py            # Composite scoring
│   ├── divergence_detector.py    # Pattern detection
│   └── signal_engine.py          # Orchestrator
│
├── dashboard/
│   ├── __init__.py
│   └── app.py                    # Streamlit UI
│
├── utils/
│   ├── __init__.py
│   ├── config.py                 # All config (weights, thresholds, colors)
│   ├── cache.py                  # TTL file caching (json + pickle)
│   ├── logger.py                 # Structured logging
│   ├── validators.py             # Schema validation
│   └── mock_data.py              # Test data generator
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_data_sources.py
│   ├── test_signal_engine.py
│   └── test_divergence.py
│
├── notebooks/
│   └── backtesting.ipynb         # Performance analysis outline
│
├── .streamlit/
│   └── config.toml               # Dark mode + server config
│
├── requirements.txt
├── pytest.ini
├── README.md
└── .gitignore
```

---

## Quick Start

### Local Development

```bash
git clone https://github.com/yourusername/signalstack.git
cd signalstack
pip install -r requirements.txt
streamlit run dashboard/app.py
```

Dashboard at: http://localhost:8501

### Run Tests

```bash
# Pure-logic tests only (fast, no network)
pytest -m "not network"

# Full suite (hits live APIs)
pytest
```

---

## Deployment (Streamlit Cloud)

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial SignalStack"
   git remote add origin https://github.com/yourusername/signalstack.git
   git push -u origin main
   ```

2. **Connect to Streamlit Cloud:**
   - Go to https://share.streamlit.io
   - "New app"
   - Repo: `yourusername/signalstack`
   - Branch: `main`
   - File path: `dashboard/app.py`
   - Deploy

That is it — your dashboard is live and refreshes data every 15 minutes.

---

## How This Maps to Web3 / Crypto Hiring

This project demonstrates:

- **API integration:** reliably calling multiple free public APIs with rate limit handling, retries, timeouts
- **Data pipelines:** multi-source ingestion, normalization, schema validation, caching
- **Signal engineering:** composite scoring with weights and confidence, explainable divergence patterns, no black boxes
- **Production mindset:** type hints, docstrings, structured logging, unit tests, config-driven, cloud-deployable

### Common Interview Questions

**"How would you optimize this for real-time?"**
Deploy to AWS Lambda + DynamoDB. Cache in Redis. Stream updates via WebSocket instead of Streamlit reruns.

**"What if Farside's HTML changes?"**
Fallback to alternative ETF data source (e.g., CoinGecko derivatives endpoint). Monitor table structure; alert on parse errors. The current scraper returns stale-cached data when parsing fails.

**"How do you handle missing data?"**
Reduce confidence score proportionally. Compute partial Flow Score from available sources. Flag in UI ("ETF data unavailable").

**"Can you backtest this?"**
Yes. Store daily Flow Scores + price in CSV. Compute hit rates and forward returns. See `notebooks/backtesting.ipynb`.

---

## Disclaimer

This tool is for educational purposes only. SignalStack is **NOT** financial advice. Crypto markets are highly volatile. Do **NOT** trade based solely on these signals. Always conduct your own research and consult a financial advisor before investing.

---

## License

MIT.
