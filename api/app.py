import os, json, requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from requests.auth import HTTPBasicAuth

app = FastAPI()

# --- Static files (serve the UI) ---
app.mount("/assets", StaticFiles(directory="web"), name="assets")

# Root route -> serve index.html
@app.get("/")
def root():
    return FileResponse("web/index.html")

# --- Trading 212 config ---
BASE_URL = os.getenv("T212_BASE_URL", "https://live.trading212.com")
ENDPOINT = "/api/v0/equity/account/cash"
HEADERS = {"Accept": "application/json"}

ACCOUNTS: Dict[str, Dict[str, Dict[str, str]]] = {
    "Louis": {
        "Invest": {
            "API_KEY_ID": os.getenv("LOUIS_INVEST_ID", ""),
            "API_SECRET_KEY": os.getenv("LOUIS_INVEST_SECRET", ""),
        },
        "Stocks ISA": {
            "API_KEY_ID": os.getenv("LOUIS_ISA_ID", ""),
            "API_SECRET_KEY": os.getenv("LOUIS_ISA_SECRET", ""),
        },
    },
    "Rebecca": {
        "Stocks ISA": {
            "API_KEY_ID": os.getenv("REBECCA_ISA_ID", ""),
            "API_SECRET_KEY": os.getenv("REBECCA_ISA_SECRET", ""),
        }
    },
    "Johnny": {
        "Invest": {
            "API_KEY_ID": os.getenv("JOHNNY_INVEST_ID", ""),
            "API_SECRET_KEY": os.getenv("JOHNNY_INVEST_SECRET", ""),
        },
        "Stocks ISA": {
            "API_KEY_ID": os.getenv("JOHNNY_ISA_ID", ""),
            "API_SECRET_KEY": os.getenv("JOHNNY_ISA_SECRET", ""),
        },
    },
}

def as_float(x: Any) -> float:
    try: return float(x) if x is not None else 0.0
    except Exception: return 0.0

def fetch_cash_balance(api_key_id: str, api_secret_key: str) -> Dict[str, Any]:
    r = requests.get(BASE_URL + ENDPOINT, headers=HEADERS,
                     auth=HTTPBasicAuth(api_key_id, api_secret_key), timeout=20)
    if r.status_code == 200: return r.json()
    return {"error": f"{r.status_code}: {r.text}"}

def get_latest_exchange_rate(base_currency, target_currency):
    # try last 7 days to avoid weekend gaps
    for i in range(7):
        d = (datetime.now(timezone.utc).date() - timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://api.frankfurter.app/{d}?from={base_currency}&to={target_currency}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                rate = resp.json().get("rates", {}).get(target_currency)
                if rate: return float(rate)
        except requests.exceptions.RequestException:
            pass
    raise RuntimeError("FX lookup failed")

@app.get("/healthz")
def healthz():
    return {"ok": True}

@app.get("/balances")
def balances():
    try:
        try:
            usd_to_gbp = get_latest_exchange_rate("USD", "GBP")
        except Exception:
            usd_to_gbp = None

        by_person = {}
        grand = {"free_gbp": 0.0, "portfolio_gbp": 0.0, "total_gbp": 0.0}
        accounts_out = []

        for person, accounts in ACCOUNTS.items():
            p_tot = by_person.setdefault(person, {"free_gbp": 0.0, "portfolio_gbp": 0.0, "total_gbp": 0.0})

            for acc_type, creds in accounts.items():
                data = fetch_cash_balance(creds["API_KEY_ID"], creds["API_SECRET_KEY"])
                if "error" in data:
                    accounts_out.append({"person": person, "account": acc_type, "error": data["error"]})
                    continue

                free = as_float(data.get("free"))
                invested_cost = as_float(data.get("invested"))
                ppl = as_float(data.get("ppl"))        # unrealised P/L
                total = as_float(data.get("total"))
                portfolio = invested_cost + ppl        # “Portfolio Value”

                # Johnny/Invest displays $ but summaries in £
                display_currency = "GBP"
                fx = 1.0
                if person == "Johnny" and acc_type == "Invest":
                    display_currency = "USD"
                    if usd_to_gbp: fx = usd_to_gbp

                # Summaries in GBP
                p_tot["free_gbp"] += free * fx
                p_tot["portfolio_gbp"] += portfolio * fx
                p_tot["total_gbp"] += total * fx
                grand["free_gbp"] += free * fx
                grand["portfolio_gbp"] += portfolio * fx
                grand["total_gbp"] += total * fx

                accounts_out.append({
                    "person": person,
                    "account": acc_type,
                    "displayCurrency": display_currency,
                    "free": free,
                    "portfolio": portfolio,
                    "total": total,
                })

        body = {
            "asOf": datetime.now(timezone.utc).isoformat(),
            "accounts": accounts_out,
            "summary": {"grand": grand, "byPerson": by_person}
        }
        return JSONResponse(content=body, headers={"Cache-Control": "no-store"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})