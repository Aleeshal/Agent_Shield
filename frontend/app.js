// AgentShield frontend: calls the backend API and fills the page. No build step.

const $ = (id) => document.getElementById(id);

const state = {
  chatbot: null,
  runs: [],
  run: null,        // run currently shown
  filter: "all",
  open: new Set(),  // expanded result rows
  compare: null,
  polling: null,
};

const OUTCOME_LABEL = {
  pass: "Pass",
  confirmed_fail: "Confirmed fail",
  suspected_fail: "Suspected fail",
  inconclusive: "Inconclusive",
};
const CHANGE_LABEL = {
  fixed: "Fixed",
  regressed: "Regressed",
  still_failing: "Still failing",
  still_passing: "Still passing",
  changed: "Changed",
  new: "New",
  removed: "Removed",
};

// ---------- helpers ----------

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

const pretty = (s) => String(s).replace(/_/g, " ");

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const d = data && data.detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join("; ") : res.statusText;
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}

async function busy(btn, label, fn) {
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spin"></span>${esc(label)}`;
  try { return await fn(); }
  finally { btn.disabled = false; btn.innerHTML = old; }
}

function showError(msg) {
  const el = $("run-error");
  el.textContent = msg;
  el.classList.toggle("hidden", !msg);
}

const outBadge = (o) => `<span class="out ${esc(o || "none")}">${esc(OUTCOME_LABEL[o] || "—")}</span>`;
const fmtTime = (iso) => new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

// ---------- status + steps ----------

async function loadHealth() {
  const el = $("status");
  try {
    const h = await api("/api/health");
    if (h.mock) {
      el.className = "status mock";
      $("status-text").textContent = "Mock mode (no model calls)";
    } else if (!h.api_key_set) {
      el.className = "status bad";
      $("status-text").textContent = "NEBIUS_API_KEY not set";
    } else {
      el.className = "status ok";
      $("status-text").textContent = `Nebius · ${h.model}`;
    }
    el.title = `Chatbot model: ${h.model}\nJudge model: ${h.judge_model}`;
  } catch {
    el.className = "status bad";
    $("status-text").textContent = "Backend unreachable";
  }
}

function renderSteps() {
  const run = state.run;
  const done = {
    1: !!run,
    2: !!run && run.status === "done",
    3: !!state.chatbot && !state.chatbot.is_default,
    4: !!state.compare,
  };
  const firstOpen = [1, 2, 3, 4].find((n) => !done[n]);
  document.querySelectorAll(".steps li").forEach((li) => {
    const n = Number(li.dataset.step);
    li.classList.toggle("done", done[n]);
    li.classList.toggle("active", n === firstOpen);
  });
}

// ---------- chatbot ----------

function renderChatbot() {
  const c = state.chatbot;
  $("bot-name").textContent = c.name;
  $("bot-desc").textContent = c.description;
  $("bot-rules").innerHTML = c.rules.map((r) => `<li><b>${esc(r.id)}</b><span>${esc(r.text)}</span></li>`).join("");
  $("bot-protected").innerHTML = c.protected_values.map((p) => `<span class="chip">${esc(p.label)}</span>`).join("");
  $("instructions").value = c.instructions;
  const badge = $("bot-badge");
  badge.textContent = c.is_default ? "default instructions" : "modified instructions";
  badge.className = c.is_default ? "badge" : "badge green";
  renderSteps();
  renderRunIntro();
}

async function loadChatbot() {
  state.chatbot = await api("/api/chatbot");
  renderChatbot();
}

async function saveInstructions(text) {
  state.chatbot = await api("/api/chatbot/instructions", { method: "PUT", body: { instructions: text } });
  renderChatbot();
}

// ---------- runs ----------

function retestParent() {
  // A run is a retest when instructions changed since the shown finished run.
  const r = state.run;
  if (r && r.status === "done" && state.chatbot && r.instructions !== state.chatbot.instructions) return r;
  return null;
}

function renderRunIntro() {
  if (state.polling) return;
  const parent = retestParent();
  $("run-title").textContent = parent ? "Retest with the new instructions" : "Run the attack suite";
  $("run-sub").textContent = parent
    ? `Reruns the same tests and compares against “${parent.label}” (${parent.summary?.pass_rate ?? 0}% pass).`
    : "Sends every test in the suite to the chatbot and evaluates each reply.";
  $("run-btn").textContent = parent ? "Run retest" : "Run tests";
}

async function startRun() {
  showError("");
  const parent = retestParent();
  const unsaved = $("instructions").value !== state.chatbot.instructions;
  if (unsaved && !confirm("You have unsaved instruction edits. Run with the saved instructions anyway?")) return;
  try {
    const run = await api("/api/runs", {
      method: "POST",
      body: parent ? { parent_run_id: parent.id } : {},
    });
    state.compare = null;
    $("compare-card").classList.add("hidden");
    $("fix-card").classList.add("hidden");
    showRun(run);
    poll(run.id);
  } catch (e) {
    showError(`Could not start run: ${e.message}`);
  }
}

function poll(runId) {
  clearTimeout(state.polling);
  $("run-btn").disabled = true;
  $("run-btn").innerHTML = `<span class="spin"></span>Running…`;
  const stop = () => {
    state.polling = null;
    $("run-btn").disabled = false;
    renderRunIntro();
  };
  // Chained timeouts, not setInterval: the next poll starts only after the previous reply,
  // so slow responses can't pile up or arrive out of order.
  const tick = async () => {
    try {
      const run = await api(`/api/runs/${runId}`);
      showRun(run);
      if (run.status === "running") {
        state.polling = setTimeout(tick, 1000);
        return;
      }
      stop();
      await loadRuns();
      if (run.status === "error") showError(`Run failed: ${run.error}`);
      if (run.status === "done" && run.parent_run_id) await loadCompare(run.parent_run_id, run.id);
    } catch (e) {
      stop();
      showError(`Lost contact with the backend: ${e.message}`);
    }
  };
  state.polling = setTimeout(tick, 500);
}

function showRun(run) {
  const changed = !state.run || state.run.id !== run.id;
  state.run = run;
  if (changed) { state.open.clear(); state.filter = "all"; }

  const prog = $("progress");
  const running = run.status === "running";
  prog.classList.toggle("hidden", !running);
  if (running) {
    const pct = run.total ? Math.round((100 * run.completed) / run.total) : 0;
    $("progress-bar").style.width = `${pct}%`;
    $("progress-text").textContent = `${run.completed} / ${run.total} tests evaluated`;
  }
  renderResults();
  renderFix();
  renderSteps();
  renderHistory();
}

function liveSummary(results) {
  const counts = { pass: 0, confirmed_fail: 0, suspected_fail: 0, inconclusive: 0 };
  results.forEach((r) => { counts[r.outcome] = (counts[r.outcome] || 0) + 1; });
  const total = results.length;
  return { total, counts, pass_rate: total ? Math.round((1000 * counts.pass) / total) / 10 : 0 };
}

function renderResults() {
  const run = state.run;
  const card = $("results-card");
  if (!run || !run.results.length) { card.classList.add("hidden"); return; }
  card.classList.remove("hidden");

  const s = run.summary || liveSummary(run.results);
  $("results-label").textContent = `· ${run.label} · ${fmtTime(run.created_at)}${run.mock ? " · mock" : ""}`;

  const hold = run.summary?.holdout;
  $("scores").innerHTML = `
    <div class="score main"><div class="num">${s.pass_rate}%</div><div class="lbl">Pass rate (${s.counts.pass}/${s.total})</div></div>
    <div class="score fail"><div class="num">${s.counts.confirmed_fail}</div><div class="lbl">Confirmed fails</div></div>
    <div class="score warn"><div class="num">${s.counts.suspected_fail}</div><div class="lbl">Suspected fails</div></div>
    <div class="score info"><div class="num">${s.counts.inconclusive}</div><div class="lbl">Inconclusive</div></div>
    ${hold && hold.total ? `<div class="score"><div class="num">${hold.pass_rate}%</div><div class="lbl">Holdout pass (${hold.counts.pass}/${hold.total})</div></div>` : ""}`;

  const cats = run.summary?.by_category;
  $("categories").innerHTML = cats ? Object.entries(cats).map(([name, c]) => `
    <div class="cat">
      <span class="name" title="${esc(pretty(name))}">${esc(pretty(name))}</span>
      <div class="track"><div class="fill" style="width:${c.total ? (100 * c.counts.pass) / c.total : 0}%"></div></div>
      <span class="frac">${c.counts.pass}/${c.total}</span>
    </div>`).join("") : "";

  const filters = [["all", "All"], ["fail", "Fails"], ...Object.entries(OUTCOME_LABEL)];
  $("filters").innerHTML = filters.map(([k, label]) =>
    `<button role="tab" data-filter="${k}" aria-selected="${state.filter === k}">${esc(label)}</button>`).join("");

  const rows = run.results.filter((r) =>
    state.filter === "all" ? true
      : state.filter === "fail" ? r.outcome.endsWith("_fail")
        : r.outcome === state.filter);

  $("results-body").innerHTML = rows.map((r) => {
    const open = state.open.has(r.test_id);
    const main = `<tr class="res" data-id="${esc(r.test_id)}" aria-expanded="${open}">
      <td class="id">${esc(r.test_id)}${r.holdout ? '<span class="hold" title="Hidden from the suggestion step">holdout</span>' : ""}</td>
      <td>${esc(pretty(r.category))}</td>
      <td>${outBadge(r.outcome)}</td>
      <td class="why">${esc(r.reason)}</td></tr>`;
    if (!open) return main;
    return main + `<tr class="detail"><td colspan="4"><div class="detail-grid">
      <div><h4>Attack prompt</h4><pre>${esc(r.prompt)}</pre></div>
      <div><h4>Chatbot reply</h4><pre>${esc(r.response || "(no reply)")}</pre></div>
      <div><h4>Expected behaviour</h4><p>${esc(r.expected_behavior)}</p></div>
      <div class="muted small">Rules tested: ${esc((r.target_rules || []).join(", ") || "—")}
        · Failure type: ${esc(r.failure_category ? pretty(r.failure_category) : "—")}
        · ${r.duration_s ?? "?"}s</div>
    </div></td></tr>`;
  }).join("") || `<tr><td colspan="4" class="muted">No tests match this filter.</td></tr>`;
}

// ---------- suggestions / fix ----------

function renderFix() {
  const run = state.run;
  const card = $("fix-card");
  if (!run || run.status !== "done") { card.classList.add("hidden"); return; }
  card.classList.remove("hidden");
  const visibleFails = run.results.filter((r) => r.outcome.endsWith("_fail") && !r.holdout).length;
  $("suggest-btn").textContent = run.suggestions ? "Regenerate suggestions" : "Generate suggestions";
  $("suggest-btn").disabled = visibleFails === 0;
  const sg = run.suggestions;
  const src = $("fix-source");
  src.textContent = sg ? { model: "AI generated", fallback: "rule based", none: "nothing to fix" }[sg.source] || sg.source : "";
  src.className = sg?.source === "model" ? "badge green" : "badge";
  src.classList.toggle("hidden", !sg);

  if (!sg) {
    $("fix-body").innerHTML = visibleFails === 0
      ? `<p class="sugg-summary">No visible tests failed in this run. Nothing to fix.</p>` : "";
    return;
  }
  const items = sg.suggestions.map((s) => `<li><b>${esc(s.title)}</b>${esc(s.detail)}
      ${s.test_ids?.length ? `<div class="ids">${s.test_ids.map((t) => `<code>${esc(t)}</code>`).join("")}</div>` : ""}</li>`).join("");
  $("fix-body").innerHTML = `
    ${sg.note ? `<div class="note">${esc(sg.note)}</div>` : ""}
    <p class="sugg-summary">${esc(sg.summary)}</p>
    ${items ? `<ul class="sugg">${items}</ul>` : ""}
    ${(sg.warnings || []).map((w) => `<div class="note">${esc(w)}</div>`).join("")}
    ${sg.revised_instructions ? `
      <h3>Proposed instructions (editable)</h3>
      <textarea id="revised" rows="14" spellcheck="false">${esc(sg.revised_instructions)}</textarea>
      <div class="row">
        <button class="btn primary" id="apply-retest">Apply fix &amp; retest</button>
        <button class="btn" id="apply-only">Apply fix only</button>
      </div>` : ""}`;
}

async function generateSuggestions() {
  const run = state.run;
  showError("");
  await busy($("suggest-btn"), "Thinking…", async () => {
    try {
      run.suggestions = await api(`/api/runs/${run.id}/suggestions`, { method: "POST" });
    } catch (e) {
      showError(`Could not generate suggestions: ${e.message}`);
    }
  });
  if (state.run === run) renderFix();  // after busy() restores the button, so the new label sticks
}

async function applyFix(andRetest) {
  const text = $("revised").value.trim();
  if (!text) return;
  try {
    await saveInstructions(text);
    if (andRetest) {
      await startRun();
      $("results-card").scrollIntoView({ behavior: "smooth", block: "start" });
    }
  } catch (e) {
    showError(`Could not apply fix: ${e.message}`);
  }
}

// ---------- comparison ----------

async function loadCompare(beforeId, afterId) {
  try {
    state.compare = await api(`/api/compare?before=${encodeURIComponent(beforeId)}&after=${encodeURIComponent(afterId)}`);
    renderCompare();
  } catch (e) {
    showError(`Could not compare runs: ${e.message}`);
  }
}

function renderCompare() {
  const c = state.compare;
  const card = $("compare-card");
  renderSteps();
  if (!c) { card.classList.add("hidden"); return; }
  card.classList.remove("hidden");
  const d = c.pass_rate_delta;
  const hb = c.before.summary.holdout, ha = c.after.summary.holdout;
  const order = ["fixed", "regressed", "still_failing", "changed", "still_passing", "new", "removed"];
  const rows = [...c.rows].sort((a, b) => order.indexOf(a.change) - order.indexOf(b.change));
  $("compare-body").innerHTML = `
    <div class="cmp-head">
      <div class="cmp-side"><div class="num">${c.before.summary.pass_rate}%</div><div class="lbl">Before · ${esc(c.before.label)}</div></div>
      <div class="cmp-delta ${d > 0 ? "up" : d < 0 ? "down" : ""}">${d > 0 ? "+" : ""}${d} pts</div>
      <div class="cmp-side"><div class="num">${c.after.summary.pass_rate}%</div><div class="lbl">After · ${esc(c.after.label)}</div></div>
    </div>
    <div class="cmp-chips">
      ${order.filter((k) => c.changes[k]).map((k) => `<span class="out ${k}">${c.changes[k]} ${esc(CHANGE_LABEL[k])}</span>`).join("")}
    </div>
    ${hb.total ? `<p class="muted small">Holdout tests (never shown to the suggestion step): ${hb.pass_rate}% → ${ha.pass_rate}%. ${
      c.holdout_pass_rate_delta > 0 ? "The fix generalised beyond the tests it was built from." :
      c.holdout_pass_rate_delta < 0 ? "Holdout got worse: the fix may be overfitted." : "No change on holdout."}</p>` : ""}
    <div class="table-wrap"><table>
      <thead><tr><th>Test</th><th>Category</th><th>Before → After</th><th>Change</th></tr></thead>
      <tbody>${rows.map((r) => `<tr>
        <td class="id">${esc(r.test_id)}${r.holdout ? '<span class="hold">holdout</span>' : ""}</td>
        <td>${esc(pretty(r.category))}</td>
        <td>${outBadge(r.before)}<span class="arrow">→</span>${outBadge(r.after)}</td>
        <td><span class="out ${esc(r.change)}">${esc(CHANGE_LABEL[r.change] || r.change)}</span></td>
      </tr>`).join("")}</tbody>
    </table></div>`;
}

// ---------- history ----------

async function loadRuns() {
  state.runs = await api("/api/runs");
  renderHistory();
}

function renderHistory() {
  const done = state.runs.filter((r) => r.status === "done");
  $("history").innerHTML = state.runs.map((r) => `
    <li data-id="${esc(r.id)}" class="${state.run && state.run.id === r.id ? "current" : ""}">
      <div><div>${esc(r.label)}${r.mock ? ' <span class="badge">mock</span>' : ""}</div>
        <div class="meta">${fmtTime(r.created_at)} · ${esc(r.status)}${r.status === "running" ? ` ${r.completed}/${r.total}` : ""}</div></div>
      <span class="rate">${r.summary ? `${r.summary.pass_rate}%` : "—"}</span>
    </li>`).join("") || `<li class="muted">No runs yet. Press “Run tests” to start.</li>`;

  const opts = done.map((r) => `<option value="${esc(r.id)}">${esc(r.label)} · ${fmtTime(r.created_at)} · ${r.summary.pass_rate}%</option>`).join("");
  // Default: before = second-newest, after = newest. Keep a choice only if the user made one.
  for (const [id, idx] of [["pick-before", 1], ["pick-after", 0]]) {
    const sel = $(id);
    const keep = sel.dataset.touched ? sel.value : null;
    sel.innerHTML = opts;
    if (keep && done.some((r) => r.id === keep)) sel.value = keep;
    else if (done[idx]) sel.value = done[idx].id;
  }
  $("pick-compare").disabled = done.length < 2;
}

async function openRun(id) {
  if (state.polling) return;
  try {
    const run = await api(`/api/runs/${id}`);
    showRun(run);
    renderRunIntro();
    if (run.status === "running") poll(run.id);
    if (run.status === "done" && run.parent_run_id) await loadCompare(run.parent_run_id, run.id);
    else { state.compare = null; renderCompare(); }
  } catch (e) {
    showError(e.message);
  }
}

// ---------- custom attack ----------

async function sendAttack() {
  const prompt = $("attack-prompt").value.trim();
  if (!prompt) return;
  await busy($("attack-send"), "Sending…", async () => {
    try {
      const r = await api("/api/attack", { method: "POST", body: { prompt } });
      $("attack-result").innerHTML = `
        <div>${outBadge(r.outcome)}</div>
        <pre>${esc(r.response)}</pre>
        <p class="muted small">${esc(r.reason)}</p>`;
    } catch (e) {
      $("attack-result").innerHTML = `<div class="error">${esc(e.message)}</div>`;
    }
  });
}

// ---------- wiring ----------

function wire() {
  $("run-btn").addEventListener("click", startRun);
  $("save-instr").addEventListener("click", (e) => busy(e.currentTarget, "Saving…", async () => {
    try { await saveInstructions($("instructions").value); } catch (err) { showError(err.message); }
  }));
  $("reset-instr").addEventListener("click", (e) => busy(e.currentTarget, "Resetting…", async () => {
    try {
      state.chatbot = await api("/api/chatbot/reset", { method: "POST" });
      renderChatbot();
    } catch (err) { showError(err.message); }
  }));
  $("suggest-btn").addEventListener("click", generateSuggestions);
  $("attack-send").addEventListener("click", sendAttack);
  for (const id of ["pick-before", "pick-after"]) {
    $(id).addEventListener("change", (e) => { e.target.dataset.touched = "1"; });
  }
  $("pick-compare").addEventListener("click", () => {
    const b = $("pick-before").value, a = $("pick-after").value;
    if (!b || !a) return;
    if (b === a) { showError("Pick two different runs to compare."); return; }
    showError("");
    loadCompare(b, a).then(() => $("compare-card").scrollIntoView({ behavior: "smooth" }));
  });

  $("filters").addEventListener("click", (e) => {
    const f = e.target.closest("button")?.dataset.filter;
    if (f) { state.filter = f; renderResults(); }
  });
  $("results-body").addEventListener("click", (e) => {
    const tr = e.target.closest("tr.res");
    if (!tr) return;
    const id = tr.dataset.id;
    state.open.has(id) ? state.open.delete(id) : state.open.add(id);
    renderResults();
  });
  $("fix-body").addEventListener("click", (e) => {
    if (e.target.id === "apply-retest") applyFix(true);
    if (e.target.id === "apply-only") applyFix(false);
  });
  $("history").addEventListener("click", (e) => {
    const li = e.target.closest("li[data-id]");
    if (li) openRun(li.dataset.id);
  });
}

async function init() {
  wire();
  await loadHealth();
  try {
    await loadChatbot();
    await loadRuns();
    const latest = state.runs[0];
    if (latest) await openRun(latest.id);
  } catch (e) {
    showError(`Could not load data from the backend: ${e.message}`);
  }
  renderSteps();
}

init();
