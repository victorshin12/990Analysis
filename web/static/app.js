(() => {
  const state = {
    dataset: "delegation",
    page: 1,
    meta: null,
    charts: {},
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
    $("charts_panel").classList.toggle("hidden", !isDel);

    if (isDel) {
      fillSelect($("state"), state.meta.options.states || []);
    }
    $("table_title").textContent = state.meta.label;
  }

  function syncDownloadLink() {
    const params = currentParams();
    params.delete("page");
    params.delete("page_size");
    $("download").href = `/api/download/${state.dataset}?${params.toString()}`;
    $("download").download = `${state.dataset}_filtered.csv`;
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
    syncDownloadLink();
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

  async function loadCharts() {
    if (state.dataset !== "delegation") return;
    const params = currentParams();
    params.delete("page");
    params.delete("page_size");
    await loadDelegationCharts(params);
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

  switchTab("delegation");
})();
