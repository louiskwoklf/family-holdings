import os, json, requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from requests.auth import HTTPBasicAuth

app = FastAPI()
app.mount("/assets", StaticFiles(directory="web"), name="assets")

@app.get("/")
def root():
    return FileResponse("web/index.html")

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

PERSON_ALIASES = {
    "Rebecca": "Johnny and Rebecca",
    "Johnny": "Johnny and Rebecca",
}

def as_float(x: Any) -> float:
    try:
        return float(x) if x is not None else 0.0
    except Exception:
        return 0.0

def fetch_cash_balance(api_key_id: str, api_secret_key: str) -> Dict[str, Any]:
    r = requests.get(
        BASE_URL + ENDPOINT,
        headers=HEADERS,
        auth=HTTPBasicAuth(api_key_id, api_secret_key),
        timeout=20,
    )
    if r.status_code == 200:
        return r.json()
    return {"error": f"{r.status_code}: {r.text}"}

def get_latest_exchange_rate(base_currency: str, target_currency: str) -> float:
    for i in range(7):
        d = (datetime.now(timezone.utc).date() - timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://api.frankfurter.app/{d}?from={base_currency}&to={target_currency}"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                rate = resp.json().get("rates", {}).get(target_currency)
                if rate:
                    return float(rate)
        except requests.exceptions.RequestException:
            pass
    raise RuntimeError("FX lookup failed")

def get_fx_rates_from_gbp() -> Dict[str, Any]:
    for i in range(7):
        d = (datetime.now(timezone.utc).date() - timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"https://api.frankfurter.app/{d}?from=GBP&to=USD,HKD"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                j = resp.json()
                rates = j.get("rates", {})
                usd = float(rates.get("USD")) if rates.get("USD") is not None else None
                hkd = float(rates.get("HKD")) if rates.get("HKD") is not None else None
                if usd is not None or hkd is not None:
                    return {"date": j.get("date", d), "USD": usd, "HKD": hkd}
        except requests.exceptions.RequestException:
            pass
    return {"date": None, "USD": None, "HKD": None}

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

        by_person: Dict[str, Dict[str, float]] = {}
        grand = {"free_gbp": 0.0, "portfolio_gbp": 0.0, "total_gbp": 0.0}
        accounts_by_person: Dict[str, List[Dict[str, Any]]] = {}

        for person, accounts in ACCOUNTS.items():
            alias = PERSON_ALIASES.get(person, person)
            p_tot = by_person.setdefault(
                alias, {"free_gbp": 0.0, "portfolio_gbp": 0.0, "total_gbp": 0.0}
            )
            person_accounts = accounts_by_person.setdefault(alias, [])

            for acc_type, creds in accounts.items():
                data = fetch_cash_balance(creds["API_KEY_ID"], creds["API_SECRET_KEY"])
                if "error" in data:
                    person_accounts.append({"person": alias, "account": acc_type, "error": data["error"]})
                    continue

                free = as_float(data.get("free"))
                invested_cost = as_float(data.get("invested"))
                ppl = as_float(data.get("ppl"))
                total = as_float(data.get("total"))
                portfolio = invested_cost + ppl

                display_currency = "GBP"
                fx = 1.0
                if person == "Johnny" and acc_type == "Invest":
                    display_currency = "USD"
                    if usd_to_gbp:
                        fx = usd_to_gbp

                p_tot["free_gbp"] += free * fx
                p_tot["portfolio_gbp"] += portfolio * fx
                p_tot["total_gbp"] += total * fx
                grand["free_gbp"] += free * fx
                grand["portfolio_gbp"] += portfolio * fx
                grand["total_gbp"] += total * fx

                person_accounts.append({
                    "person": alias,
                    "account": acc_type,
                    "displayCurrency": display_currency,
                    "free": free,
                    "portfolio": portfolio,
                    "total": total,
                })

        def account_sort_key(acc: Dict[str, Any]) -> float:
            if acc.get("error"):
                return float("-inf")
            total = as_float(acc.get("total"))
            if acc.get("displayCurrency") == "USD" and usd_to_gbp:
                return total * usd_to_gbp
            return total

        accounts_out: List[Dict[str, Any]] = []
        for person in by_person.keys():
            person_accounts = accounts_by_person.get(person, [])
            accounts_out.extend(sorted(person_accounts, key=account_sort_key, reverse=True))

        fx_snapshot = get_fx_rates_from_gbp()
        total_gbp = grand["total_gbp"]
        total_usd = total_hkd = None
        if fx_snapshot.get("USD") is not None:
            total_usd = total_gbp * fx_snapshot["USD"]
        if fx_snapshot.get("HKD") is not None:
            total_hkd = total_gbp * fx_snapshot["HKD"]

        body = {
            "asOf": datetime.now(timezone.utc).isoformat(),
            "accounts": accounts_out,
            "summary": {"grand": grand, "byPerson": by_person},
            "grandTotals": {
                "GBP": total_gbp,
                "USD": total_usd,
                "HKD": total_hkd,
            },
            "fx": {
                "base": "GBP",
                "date": fx_snapshot.get("date"),
                "rates": {"USD": fx_snapshot.get("USD"), "HKD": fx_snapshot.get("HKD")},
            },
        }
        return JSONResponse(content=body, headers={"Cache-Control": "no-store"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
