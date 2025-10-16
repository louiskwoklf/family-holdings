const API_BASE = ""; // empty -> fetch("/balances")

const fmtGBP = (n) => `£${Number(n).toLocaleString(undefined,{minimumFractionDigits:2, maximumFractionDigits:2})}`;
const fmtUSD = (n) => `$${Number(n).toLocaleString(undefined,{minimumFractionDigits:2, maximumFractionDigits:2})}`;
const el = (sel) => document.querySelector(sel);
const tpl = (id) => document.getElementById(id).content.cloneNode(true);
const currencyFmt = (c) => (c === "USD" ? fmtUSD : fmtGBP);

async function load() {
  const asOf = el("#asOf");
  const grandTotal = el("#grand-total");
  const grandFree = el("#grand-free");
  const grandPortfolio = el("#grand-portfolio");
  const accountsGrid = el("#accounts");
  const byPerson = el("#byPerson");

  grandTotal.textContent = grandFree.textContent = grandPortfolio.textContent = "—";
  accountsGrid.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/balances`, { cache: "no-store" });
    const data = await res.json();
    asOf.textContent = data.asOf ? `As of ${new Date(data.asOf).toLocaleString()}` : "";

    grandTotal.textContent     = fmtGBP(data.summary.grand.total_gbp || 0);
    grandFree.textContent      = fmtGBP(data.summary.grand.free_gbp || 0);
    grandPortfolio.textContent = fmtGBP(data.summary.grand.portfolio_gbp || 0);

    accountsGrid.innerHTML = "";
    (data.accounts || []).forEach(acc => {
      const node = tpl("account-card");
      node.querySelector(".title").textContent = `${acc.person} — ${acc.account}`;
      const badge = node.querySelector(".badge");
      const code = acc.displayCurrency === "USD" ? "USD" : "GBP";
      badge.textContent = code;
      badge.classList.add(code.toLowerCase());

      const fmt = currencyFmt(code);
      node.querySelector(".free").textContent = fmt(acc.free);
      node.querySelector(".portfolio").textContent = fmt(acc.portfolio);
      node.querySelector(".total").textContent = fmt(acc.total);

      if (acc.error) {
        const er = node.querySelector(".error");
        er.textContent = acc.error;
        er.classList.remove("hidden");
      }
      accountsGrid.appendChild(node);
    });

    byPerson.innerHTML = "";
    const grandTotalNum = data.summary.grand.total_gbp || 0;
    Object.entries(data.summary.byPerson || {}).forEach(([person, sums]) => {
      const line = document.createElement("div");
      line.className = "person-line";
      const pct = grandTotalNum ? ((sums.total_gbp / grandTotalNum) * 100).toFixed(1) : "0.0";
      line.innerHTML = `
        <div class="left"><strong>${person}</strong><span class="pct">${pct}% of total</span></div>
        <div class="vals">
          <span>Total <span class="val">${fmtGBP(sums.total_gbp || 0)}</span></span>
          <span>Free <span class="val">${fmtGBP(sums.free_gbp || 0)}</span></span>
          <span>Portfolio <span class="val">${fmtGBP(sums.portfolio_gbp || 0)}</span></span>
        </div>`;
      byPerson.appendChild(line);
    });
  } catch (e) {
    accountsGrid.innerHTML = `<div class="card"><div class="error">Failed to load: ${String(e)}</div></div>`;
  }
}
document.addEventListener("DOMContentLoaded", load);