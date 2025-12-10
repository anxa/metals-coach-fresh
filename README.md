Metals Coach - Fresh Skeleton

This is a minimal starting skeleton for the Precious Metals Trading Coach project.

Files:
- `alpha_vantage_fetcher.py` — small helper to fetch XAU/XAG -> USD via Alpha Vantage API.
- `app.py` — minimal Streamlit app to display live gold and silver prices.
- `requirements.txt` — required packages.
- `.env.example` — example environment variables file.

Quick start

1. Create a virtual environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and set `ALPHA_VANTAGE_API_KEY`.

3. Run the Streamlit app:

```bash
streamlit run app.py
```

Notes:
- If you do not set `ALPHA_VANTAGE_API_KEY`, the app will show instructions and not attempt API calls.
- Alpha Vantage limits API call rates on free keys — avoid rapid refreshes.
