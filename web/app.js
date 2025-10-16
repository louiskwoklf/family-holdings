const API_BASE = ""; // fetch("/balances")

const fmtGBP = (n) => `£${Number(n).toLocaleString(undefined,{minimumFractionDigits:2, maximumFractionDigits:2})}`;
const fmtUSD = (n) => `$${Number(n).toLocaleString(undefined,{minimumFractionDigits:2, maximumFractionDigits:2})}`;
const el = (sel) => document.querySelector(sel);
const tpl = (id) => document.getElementById(id).content.cloneNode(true);
const currencyFmt = (c) => (c === "USD" ? fmtUSD : fmtGBP);

async function load() {
  const asOf = el("#asOf");
  const grandTotal = el("#grand-total");
  const peopleRoot = el("#people");

  grandTotal.textContent = "—";
  peopleRoot.innerHTML = "";

  try {
    const res = await fetch(`${API_BASE}/balances`, { cache: "no-store" });
    const data = await res.json();

    asOf.textContent = data.asOf ? `As of ${new Date(data.asOf).toLocaleString()}` : "";

    // GRAND (Total only)
    const grandTotalNum = data?.summary?.grand?.total_gbp || 0;
    grandTotal.textContent = fmtGBP(grandTotalNum);

    // Build a map person -> accounts[]
    const accounts = data.accounts || [];
    const byPerson = data.summary?.byPerson || {};
    const personOrder = Object.keys(byPerson); // keep object order

    personOrder.forEach((person) => {
      const personData = byPerson[person] || {};
      const personTotal = personData.total_gbp || 0;
      const pct = grandTotalNum ? ((personTotal / grandTotalNum) * 100).toFixed(1) : "0.0";

      const node = tpl("person-section");
      node.querySelector(".person-name").textContent = person;
      node.querySelector(".person-total").textContent = fmtGBP(personTotal);
      node.querySelector(".person .pct").textContent = `${pct}% of grand total`;

      const grid = node.querySelector(".person-accounts");

      // this person's accounts
      accounts
        .filter(a => a.person === person)
        .forEach(acc => {
          const card = tpl("account-card");
          card.querySelector(".title").textContent = acc.account;

          const badge = card.querySelector(".badge");
          const code = acc.displayCurrency === "USD" ? "USD" : "GBP";
          badge.textContent = code;
          badge.classList.add(code.toLowerCase());

          // Show only TOTAL
          const fmt = currencyFmt(code);
          card.querySelector(".only-total").textContent = fmt(acc.total);

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