(() => {
  const state = {
    dataset: "delegation",
    page: 1,
    meta: null,
    charts: {},
    govOrgs: [],
    selectedEin: "",
  };

  const $ = (id) => document.getElementById(id);

  const COLORS = {
    navy: "#21295C",
    primary: "#065A82",
    teal: "#1C7293",
    gold: "#B8860B",
    muted: "#595959",
    palette: ["#B8860B", "#065A82", "#1C7293", "#21295C", "#8C6D1F", "#4A7C8C", "#7A8B99", "#C4A35A"],
  };

  function currentParams() {
    const params = new URLSearchParams();
    const q = $("q").value.trim();
    if (q) params.set("q", q);
    if ($("year_min").value) params.set("year_min", $("year_min").value);
    if ($("year_max").value) params.set("year_max", $("year_max").value);
    if (state.dataset === "delegation") {
      if ($("state").value) params.set("state", $("state").value);
      if ($("delegation_indicator").value) {
        params.set("delegation_indicator", $("delegation_indicator").value);
      }
    }
    params.set("page", String(state.page));
    params.set("page_size", $("page_size").value);
    return params;
  }

  function fillSelect(el, values, { blankLabel = "Any", selected = "" } = {}) {
    el.innerHTML = "";
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = blankLabel;
    el.appendChild(blank);
    for (const v of values) {
      const opt = document.createElement("option");
      opt.value = String(v);
      opt.textContent = String(v);
      if (String(v) === String(selected)) opt.selected = true;
      el.appendChild(opt);
    }
  }

  async function loadMeta() {
    const res = await fetch(`/api/meta/${state.dataset}`);
    state.meta = await res.json();
    const years = state.meta.options.years || [];
    fillSelect($("year_min"), years, { blankLabel: "Any", selected: years[0] || "" });
    fillSelect($("year_max"), years, {
      blankLabel: "Any",
      selected: years[years.length - 1] || "",
    });
    // Leave year selects on Any by clearing selected after fill for open range
    $("year_min").value = "";
    $("year_max").value = "";

    const isDel = state.dataset === "delegation";
    $("state_wrap").classList.toggle("hidden", !isDel);
    $("indicator_wrap").classList.toggle("hidden", !isDel);
    $("charts_panel_delegation").classList.toggle("hidden", !isDel);
    $("charts_panel_governance").classList.toggle("hidden", isDel);

    if (isDel) {
      fillSelect($("state"), state.meta.options.states || []);
    }
    $("table_title").textContent = state.meta.label;
  }

  function downloadParams(mode) {
    const params = currentParams();
    params.delete("page");
    params.delete("page_size");
    params.set("mode", mode);
    return params;
  }

  function startDownload(mode) {
    const params = downloadParams(mode);
    window.location.href = `/api/download/${state.dataset}?${params.toString()}`;
    closeDownloadModal();
  }

  function openDownloadModal() {
    $("download_modal").classList.remove("hidden");
  }

  function closeDownloadModal() {
    $("download_modal").classList.add("hidden");
  }

  function cellClass(v) {
    const s = String(v || "").toLowerCase();
    if (s === "yes") return "yes";
    if (s === "no") return "no";
    return "";
  }

  const COLUMN_LABELS = {
    tax_year: "tax_year (filing year)",
    tax_period: "tax_period (YYYYMM end)",
  };

  function renderTable(payload) {
    const thead = document.querySelector("#results thead");
    const tbody = document.querySelector("#results tbody");
    thead.innerHTML = "";
    tbody.innerHTML = "";

    const hr = document.createElement("tr");
    for (const col of payload.columns) {
      const th = document.createElement("th");
      th.textContent = COLUMN_LABELS[col] || col;
      th.title =
        col === "tax_period"
          ? "Period-end YYYYMM. A 2015 tax year often ends in 2016 (e.g. 201606)."
          : col === "tax_year"
            ? "Form 990 tax year (year the fiscal year begins)."
            : col;
      hr.appendChild(th);
    }
    thead.appendChild(hr);

    for (const row of payload.rows) {
      const tr = document.createElement("tr");
      for (const col of payload.columns) {
        const td = document.createElement("td");
        const val = row[col] ?? "";
        td.textContent = val;
        td.title = val;
        const cls = cellClass(val);
        if (cls) td.className = cls;
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
    }

    $("match_count").textContent = `${payload.total.toLocaleString()} matching rows`;
    $("page_label").textContent = `Page ${payload.page} / ${payload.pages}`;
    $("prev").disabled = payload.page <= 1;
    $("next").disabled = payload.page >= payload.pages;
  }

  function upsertChart(key, canvasId, config) {
    if (state.charts[key]) state.charts[key].destroy();
    const ctx = $(canvasId).getContext("2d");
    state.charts[key] = new Chart(ctx, config);
  }

  async function loadDelegationCharts(params) {
    const res = await fetch(`/api/charts/delegation?${params.toString()}`);
    const data = await res.json();
    const yearLabels = data.years.map((y, i) => `${y}\nn=${data.n_hospital_years[i]}`);

    upsertChart("rates", "chart_rates", {
      type: "line",
      data: {
        labels: yearLabels,
        datasets: [
          { label: "Any delegation", data: data.rates.any_delegation, borderColor: COLORS.navy, tension: 0.2 },
          { label: "Parent / shared", data: data.rates.parent_shared, borderColor: COLORS.muted, tension: 0.2 },
          { label: "Peer-system", data: data.rates.peer_system, borderColor: COLORS.teal, tension: 0.2 },
          { label: "Dedicated MSO", data: data.rates.dedicated_mso, borderColor: COLORS.gold, tension: 0.2 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
        scales: { y: { title: { display: true, text: "% of hospital-years" }, beginAtZero: true } },
      },
    });

    upsertChart("events", "chart_events", {
      type: "bar",
      data: {
        labels: data.adopt_exit.years,
        datasets: [
          { label: "Adopted dedicated MSO", data: data.adopt_exit.adopt, backgroundColor: COLORS.gold },
          { label: "Ended dedicated MSO", data: data.adopt_exit.exit.map((v) => -v), backgroundColor: COLORS.teal },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
        scales: { y: { title: { display: true, text: "Filers" } } },
      },
    });

    upsertChart("states", "chart_states", {
      type: "bar",
      data: {
        labels: data.top_states.labels,
        datasets: [
          {
            label: "Hospitals with dedicated MSO",
            data: data.top_states.values,
            backgroundColor: COLORS.primary,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });

    upsertChart("managers", "chart_managers", {
      type: "bar",
      data: {
        labels: data.managers.years,
        datasets: data.managers.series.map((s, i) => ({
          label: s.label,
          data: s.data,
          backgroundColor: COLORS.palette[i % COLORS.palette.length],
          stack: "mgr",
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } } },
        scales: {
          x: { stacked: true },
          y: { stacked: true, title: { display: true, text: "Hospitals" }, beginAtZero: true },
        },
      },
    });
  }

  function renderOrgTimeline(org) {
    if (!org) {
      $("org_selection").textContent = "No organizations with ≥2 years in this filter.";
      $("org_timeline").innerHTML = "";
      return;
    }
    state.selectedEin = org.ein;
    $("org_search").value = org.name;
    $("org_results").classList.add("hidden");
    $("org_selection").textContent = `${org.name} · EIN ${org.ein}`;

    const years = Array.from({ length: 10 }, (_, i) => 2015 + i);
    const byYear = Object.fromEntries(org.records.map((r) => [r.year, r]));
    const rows = [
      ["delegation", "Management delegation"],
      ["jointventure", "Joint-venture investment"],
      ["documents", "Governing docs changed"],
      ["independence", "Board independence"],
    ];

    let html = '<div class="tlgrid"><div class="rowlabel">Measure</div>';
    html += years.map((y) => `<div class="yr">${y}</div>`).join("");
    for (const [key, label] of rows) {
      html += `<div class="rowlabel">${label}</div>`;
      for (const yr of years) {
        const r = byYear[yr];
        const v = r ? r[key] : null;
        let cls = "missing";
        let display = "—";
        if (v !== null && v !== undefined) {
          if (key === "independence") {
            cls = "num";
            display = `${Number(v).toFixed(1)}%`;
          } else {
            cls = v ? "yes" : "no";
            display = v ? "Yes" : "No";
          }
        }
        html += `<div class="${cls}" title="${yr}: ${label} — ${display}">${display}</div>`;
      }
    }
    html += '</div><div class="tllegend">Gold: Yes · Teal: No · Gray: missing · Blue: board independence %</div>';
    $("org_timeline").innerHTML = html;
  }

  function bindOrgSearch() {
    const box = $("org_search");
    const res = $("org_results");
    let timer = null;
    box.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        const q = box.value.trim().toLowerCase();
        if (q.length < 2) {
          res.classList.add("hidden");
          return;
        }
        const hits = state.govOrgs
          .filter((o) => o.name.toLowerCase().includes(q) || o.ein.includes(q))
          .slice(0, 12);
        res.innerHTML = "";
        if (!hits.length) {
          res.textContent = "No matching organizations in this filter";
          res.classList.remove("hidden");
          return;
        }
        for (const o of hits) {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.textContent = `${o.name} · EIN ${o.ein}`;
          btn.addEventListener("click", () => renderOrgTimeline(o));
          res.appendChild(btn);
        }
        res.classList.remove("hidden");
      }, 120);
    });
  }

  async function loadGovernanceCharts(params) {
    const res = await fetch(`/api/charts/governance?${params.toString()}`);
    const data = await res.json();
    state.govOrgs = data.organizations || [];

    const yearLabels = data.years.map((y, i) => `${y}\nn=${data.n_filings[i]}`);

    upsertChart("gov_rates", "chart_gov_rates", {
      type: "line",
      data: {
        labels: yearLabels,
        datasets: [
          {
            label: "Management delegation (VI.3)",
            data: data.delegation_rate,
            borderColor: COLORS.primary,
            tension: 0.2,
          },
          {
            label: "Joint-venture investment (VI.16a)",
            data: data.jointventure_rate,
            borderColor: COLORS.teal,
            tension: 0.2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
        scales: {
          y: {
            title: { display: true, text: "% of filings answering Yes" },
            min: 0,
            max: 50,
          },
        },
      },
    });

    upsertChart("gov_independence", "chart_gov_independence", {
      type: "line",
      data: {
        labels: data.years.map(
          (y, i) => `${y}\nY n=${data.independence_yes_n[i]} · N n=${data.independence_no_n[i]}`
        ),
        datasets: [
          {
            label: "Delegation = Yes",
            data: data.independence_yes,
            borderColor: COLORS.primary,
            tension: 0.2,
          },
          {
            label: "Delegation = No",
            data: data.independence_no,
            borderColor: COLORS.gold,
            tension: 0.2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
        scales: {
          y: {
            title: { display: true, text: "Mean board independence %" },
            min: 60,
            max: 90,
          },
        },
      },
    });

    const preferred =
      state.govOrgs.find((o) => o.ein === state.selectedEin) ||
      state.govOrgs.find((o) => o.ein === data.default_ein) ||
      state.govOrgs[0];
    renderOrgTimeline(preferred);
  }

  async function loadCharts() {
    const params = currentParams();
    params.delete("page");
    params.delete("page_size");
    if (state.dataset === "delegation") {
      await loadDelegationCharts(params);
    } else if (state.dataset === "governance") {
      await loadGovernanceCharts(params);
    }
  }

  async function query() {
    const params = currentParams();
    const res = await fetch(`/api/query/${state.dataset}?${params.toString()}`);
    const payload = await res.json();
    renderTable(payload);
    await loadCharts();
  }

  function resetFilters() {
    $("q").value = "";
    $("year_min").value = "";
    $("year_max").value = "";
    $("state").value = "";
    $("delegation_indicator").value = "";
    state.page = 1;
    query();
  }

  async function switchTab(dataset) {
    state.dataset = dataset;
    state.page = 1;
    document.querySelectorAll(".tab").forEach((btn) => {
      const on = btn.dataset.dataset === dataset;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    await loadMeta();
    await query();
  }

  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.dataset));
  });
  $("apply").addEventListener("click", () => {
    state.page = 1;
    query();
  });
  $("reset").addEventListener("click", resetFilters);
  $("prev").addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    query();
  });
  $("next").addEventListener("click", () => {
    state.page += 1;
    query();
  });
  $("page_size").addEventListener("change", () => {
    state.page = 1;
    query();
  });
  $("q").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      state.page = 1;
      query();
    }
  });

  $("download").addEventListener("click", openDownloadModal);
  $("download_tab").addEventListener("click", () => startDownload("tab"));
  $("download_agg").addEventListener("click", () => startDownload("aggregated"));
  $("download_cancel").addEventListener("click", closeDownloadModal);
  $("download_modal").addEventListener("click", (e) => {
    if (e.target === $("download_modal")) closeDownloadModal();
  });

  bindOrgSearch();
  switchTab("delegation");
})();
