(() => {
  const $ = (id) => document.getElementById(id);

  const dictUi = {
    data: null,
    sheetIndex: 0,
    search: "",
    category: "",
  };

  function esc(text) {
    const d = document.createElement("div");
    d.textContent = text == null ? "" : String(text);
    return d.innerHTML;
  }

  function formatCell(val) {
    if (val == null || val === "") return "—";
    if (typeof val === "number" && Number.isFinite(val)) {
      if (Math.abs(val - Math.round(val)) < 1e-9 && val > 1900 && val < 2100) {
        return String(Math.round(val));
      }
      if (Math.abs(val) >= 1000 && Math.abs(val - Math.round(val)) < 1e-9) {
        return Math.round(val).toLocaleString();
      }
      return String(val);
    }
    return String(val);
  }

  function categoryClass(category) {
    const key = String(category || "").toLowerCase();
    if (key.includes("identifier")) return "cat-identifier";
    if (key.includes("govern")) return "cat-governance";
    if (key.includes("delegat") || key.includes("mso")) return "cat-delegation";
    return "";
  }

  function dictMainRows() {
    const sheet = dictUi.data.sheets[dictUi.sheetIndex];
    let rows = sheet.rows.slice();
    const q = dictUi.search.trim().toLowerCase();
    if (q) {
      rows = rows.filter((row) =>
        Object.values(row).some((v) => String(v ?? "").toLowerCase().includes(q)),
      );
    }
    if (dictUi.category) {
      rows = rows.filter((row) => row.Category === dictUi.category);
    }
    return rows;
  }

  function renderDictionaryToolbar(sheet) {
    const bar = $("dictionary_toolbar");
    if (sheet.name !== "Data Dictionary") {
      bar.classList.add("hidden");
      bar.innerHTML = "";
      return;
    }
    bar.classList.remove("hidden");
    const categories = [...new Set(sheet.rows.map((r) => r.Category).filter(Boolean))].sort();
    const chips = [
      `<button type="button" class="dict-chip${dictUi.category ? "" : " active"}" data-cat="">All</button>`,
      ...categories.map(
        (c) =>
          `<button type="button" class="dict-chip${dictUi.category === c ? " active" : ""}" data-cat="${esc(c)}">${esc(c)}</button>`,
      ),
    ].join("");
    bar.innerHTML = `
      <label class="grow">
        <span>Search fields</span>
        <input id="dict_search" type="search" placeholder="Display name, CSV field, definition…" value="${esc(dictUi.search)}">
      </label>
      <div class="dict-chips" role="group" aria-label="Category filter">${chips}</div>
    `;
    $("dict_search").addEventListener("input", (e) => {
      dictUi.search = e.target.value;
      renderDictionaryBody();
    });
    bar.querySelectorAll(".dict-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        dictUi.category = btn.getAttribute("data-cat") || "";
        renderDictionaryToolbar(sheet);
        renderDictionaryBody();
      });
    });
  }

  function renderDictionaryCards(rows) {
    if (!rows.length) {
      return '<p class="dict-empty">No fields match your search.</p>';
    }
    return `<div class="dict-cards">${rows
      .map((row) => {
        const cat = row.Category || "";
        const badgeCls = `dict-badge ${categoryClass(cat)}`.trim();
        const completeness = row["Completeness %"];
        const populated = row["Populated rows"];
        return `<article class="dict-card">
          <div class="dict-card-head">
            <h4>${esc(row["Display name"] || row["CSV field"])}</h4>
            <code class="dict-field">${esc(row["CSV field"])}</code>
            ${cat ? `<span class="${badgeCls}">${esc(cat)}</span>` : ""}
          </div>
          <div class="dict-stats">
            ${populated != null ? `<span class="dict-stat">Populated: <strong>${esc(formatCell(populated))}</strong></span>` : ""}
            ${completeness != null ? `<span class="dict-stat">Completeness: <strong>${esc(formatCell(completeness))}%</strong></span>` : ""}
          </div>
          <dl>
            ${row.Definition ? `<dt>Definition</dt><dd>${esc(row.Definition)}</dd>` : ""}
            ${row["Values / format"] ? `<dt>Values / format</dt><dd>${esc(row["Values / format"])}</dd>` : ""}
            ${row["Suggested website use"] ? `<dt>Suggested website use</dt><dd>${esc(row["Suggested website use"])}</dd>` : ""}
            ${row["Notes / source"] ? `<dt>Notes / source</dt><dd>${esc(row["Notes / source"])}</dd>` : ""}
          </dl>
        </article>`;
      })
      .join("")}</div>`;
  }

  function cellHtml(raw) {
    const text = formatCell(raw);
    if (text === "—") return `<td><span class="dict-cell-empty">—</span></td>`;
    // Clamp + expand are enabled only after layout proves the text is truncated.
    return `<td>
      <div class="dict-cell dict-cell-clamp" data-expanded="false">
        <div class="dict-cell-text">${esc(text)}</div>
        <button type="button" class="dict-expand hidden" aria-expanded="false">Show more</button>
      </div>
    </td>`;
  }

  function renderDictionaryTable(sheet) {
    if (!sheet.rows.length) {
      return '<p class="dict-empty">This section is empty.</p>';
    }
    const head = sheet.columns.map((col) => `<th scope="col">${esc(col)}</th>`).join("");
    const body = sheet.rows
      .map((row) => `<tr>${sheet.columns.map((col) => cellHtml(row[col])).join("")}</tr>`)
      .join("");
    return `<div class="dict-table-wrap">
      <table class="dict-table">
        <thead><tr>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
  }

  function finalizeExpandControls(root) {
    root.querySelectorAll(".dict-cell-clamp").forEach((cell) => {
      const textEl = cell.querySelector(".dict-cell-text");
      const btn = cell.querySelector(".dict-expand");
      if (!textEl || !btn) return;

      cell.setAttribute("data-expanded", "false");
      const truncated = textEl.scrollHeight - textEl.clientHeight > 1;
      if (!truncated) {
        cell.classList.remove("dict-cell-clamp");
        btn.remove();
        return;
      }

      btn.classList.remove("hidden");
      btn.addEventListener("click", () => {
        const open = cell.getAttribute("data-expanded") === "true";
        cell.setAttribute("data-expanded", open ? "false" : "true");
        btn.setAttribute("aria-expanded", open ? "false" : "true");
        btn.textContent = open ? "Show more" : "Show less";
      });
    });
  }

  function renderDictionaryBody() {
    const sheet = dictUi.data.sheets[dictUi.sheetIndex];
    const body = $("dictionary_body");
    if (sheet.name === "Data Dictionary") {
      const rows = dictMainRows();
      body.innerHTML = renderDictionaryCards(rows);
      const summary = document.createElement("p");
      summary.className = "meta";
      summary.style.marginTop = "10px";
      summary.textContent = `${rows.length} field${rows.length === 1 ? "" : "s"} shown`;
      body.appendChild(summary);
    } else {
      body.innerHTML = renderDictionaryTable(sheet);
      requestAnimationFrame(() => finalizeExpandControls(body));
    }
  }

  function renderDictionarySheets() {
    const nav = $("dictionary_sheets");
    nav.innerHTML = dictUi.data.sheets
      .map(
        (sheet, i) =>
          `<button type="button" class="dictionary-sheet-btn${i === dictUi.sheetIndex ? " active" : ""}" data-idx="${i}">${esc(sheet.name)}</button>`,
      )
      .join("");
    nav.querySelectorAll(".dictionary-sheet-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        dictUi.sheetIndex = Number(btn.getAttribute("data-idx"));
        const sheet = dictUi.data.sheets[dictUi.sheetIndex];
        renderDictionarySheets();
        renderDictionaryToolbar(sheet);
        renderDictionaryBody();
      });
    });
  }

  async function init() {
    const body = $("dictionary_body");
    try {
      let res = await fetch("/static/data_dictionary.json");
      if (!res.ok) res = await fetch("/api/dictionary");
      if (!res.ok) throw new Error("fetch failed");
      dictUi.data = await res.json();
      dictUi.sheetIndex = 0;
      renderDictionarySheets();
      renderDictionaryToolbar(dictUi.data.sheets[0]);
      renderDictionaryBody();
    } catch (err) {
      body.innerHTML = "<p>Could not load the data dictionary.</p>";
    }
  }

  init();
})();
