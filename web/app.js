const API_BASE = "";

const fmt = {
  GBP: (n) => `£${Number(n).toLocaleString(undefined,{minimumFractionDigits:2, maximumFractionDigits:2})}`,
  USD: (n) => `$${Number(n).toLocaleString(undefined,{minimumFractionDigits:2, maximumFractionDigits:2})}`,
  HKD: (n) => `HK$${Number(n).toLocaleString(undefined,{minimumFractionDigits:2, maximumFractionDigits:2})}`,
};

const el  = (sel) => document.querySelector(sel);
const tpl = (id)  => document.getElementById(id).content.cloneNode(true);
const currencyFmt = (c) => (fmt[c] || fmt.GBP);

let grandSnapshot = { GBP: 0, USD: null, HKD: null };
let currentCCY = "GBP";

function setGrandDisplay(ccy) {
  currentCCY = ccy;
  const out  = el("#grand-total");
  const note = el("#grand-note");

  const val = grandSnapshot[ccy];
  if (val == null) {
    out.textContent = "—";
    note.textContent = "FX unavailable for this currency (server snapshot)";
    return;
  }
  out.textContent = currencyFmt(ccy)(val);
  note.textContent = (ccy === "GBP") ? "" : "Converted server-side from GBP (snapshot)";
}

function wireCurrencyToggle() {
  const group = el(".currency-toggle");
  group.addEventListener("click", (e) => {
    const btn = e.target.closest("button.pill");
    if (!btn) return;
    group.querySelectorAll(".pill").forEach(b => b.setAttribute("aria-selected", String(b === btn)));
    setGrandDisplay(btn.dataset.ccy);
  });
}

async function load() {
  const asOf = el("#asOf");
  const peopleRoot = el("#people");

  peopleRoot.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/balances`, { cache: "no-store" });
    const data = await res.json();

    asOf.textContent = data.asOf ? `As of ${new Date(data.asOf).toLocaleString()}` : "";

    grandSnapshot = {
      GBP: Number(data?.grandTotals?.GBP ?? 0),
      USD: data?.grandTotals?.USD != null ? Number(data.grandTotals.USD) : null,
      HKD: data?.grandTotals?.HKD != null ? Number(data.grandTotals.HKD) : null,
    };
    wireCurrencyToggle();
    setGrandDisplay("GBP");

    const accounts = data.accounts || [];
    const byPerson = data.summary?.byPerson || {};
    const grandTotalNum = Number(data?.summary?.grand?.total_gbp || 0);
    const personOrder = Object.keys(byPerson);

    personOrder.forEach((person) => {
      const personData = byPerson[person] || {};
      const personTotal = Number(personData.total_gbp || 0);
      const pct = grandTotalNum ? ((personTotal / grandTotalNum) * 100).toFixed(1) : "0.0";

      const node = tpl("person-section");
      node.querySelector(".person-name").textContent = person;
      node.querySelector(".person-total").textContent = fmt.GBP(personTotal);
      node.querySelector(".person .pct").textContent = `${pct}% of grand total`;

      const grid = node.querySelector(".person-accounts");

      accounts
        .filter(a => a.person === person)
        .forEach(acc => {
          const card = tpl("account-card");
          card.querySelector(".title").textContent = acc.account;

          const badge = card.querySelector(".badge");
          const code = acc.displayCurrency === "USD" ? "USD" : "GBP";
          badge.textContent = code;
          badge.classList.add(code.toLowerCase());

          const fmtFn = currencyFmt(code);
          card.querySelector(".only-total").textContent = fmtFn(acc.total);

          if (acc.error) {
            const er = card.querySelector(".error");
            er.textContent = acc.error;
            er.classList.remove("hidden");
          }
          grid.appendChild(card);
        });

      peopleRoot.appendChild(node);
    });

  } catch (e) {
    peopleRoot.innerHTML = `<div class="card"><div class="error">Failed to load: ${String(e)}</div></div>`;
  }
}

document.addEventListener("DOMContentLoaded", load);
