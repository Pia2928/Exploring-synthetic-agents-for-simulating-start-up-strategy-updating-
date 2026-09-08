// Founder Cognition Lab -- client-side logic. Talks only to the local Flask
// API at /api/... ; the Anthropic key never touches the browser.

let agents = [];
let editingAgentId = null;   // null = building a new agent
let chatAgentId = null;
let alignmentStrategies = {};
let founderIdentityDescriptions = {};
let constructionTiers = {};
let selectedStrategy = "visionary";
let selectedTier = "trait";

function agentColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  const hue = Math.abs(hash) % 360;
  return `hsl(${hue} 42% 40%)`;
}

function showToast(msg) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 4500);
}

function escapeHtml(s) {
  return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function api(path, options) {
  const res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, options));
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

function dominantIdentity(fi) {
  const entries = [["Missionary", fi.missionary], ["Darwinian", fi.darwinian], ["Communitarian", fi.communitarian]];
  entries.sort((a, b) => b[1] - a[1]);
  return entries[0][0];
}

// ---------------------------------------------------------------------------
// Page navigation
// ---------------------------------------------------------------------------

function switchPage(page) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.page === page));
  ['build', 'library', 'chat', 'individual', 'group', 'guidance'].forEach(p => {
    document.getElementById('page-' + p).style.display = (p === page) ? 'block' : 'none';
  });
  if (page === 'library') renderLibrary();
  if (page === 'guidance') renderGuidance();
}

// ---------------------------------------------------------------------------
// Load reference data + agents
// ---------------------------------------------------------------------------

async function loadReference() {
  try {
    const ref = await api('/api/reference');
    alignmentStrategies = ref.alignment_strategies;
    founderIdentityDescriptions = ref.founder_identity_descriptions;
    constructionTiers = ref.construction_tiers;
    renderTierOptions();
    renderStrategyOptions();
  } catch (e) {
    showToast("Couldn't load reference data from the server.");
  }
}

async function loadAgents() {
  try {
    agents = await api('/api/agents');
  } catch (e) {
    agents = [];
    showToast("Couldn't load agents from the server.");
  }
  renderParticipantPicker('individualParticipantPicker');
  renderParticipantPicker('groupParticipantPicker');
  renderChatAgentSelect();
  renderLibrary();
}

function renderParticipantPicker(elementId) {
  const el = document.getElementById(elementId);
  if (agents.length === 0) { el.innerHTML = `<span class="placeholder-small">Create an agent first.</span>`; return; }
  el.innerHTML = agents.map(a =>
    `<label><input type="checkbox" class="participant-cb-${elementId}" value="${a.id}" checked /> ${escapeHtml(a.name)}</label>`
  ).join('');
}

function selectedParticipantIds(elementId) {
  return Array.from(document.querySelectorAll(`.participant-cb-${elementId}:checked`)).map(cb => cb.value);
}

function renderChatAgentSelect() {
  const sel = document.getElementById('chatAgentSelect');
  const current = sel.value;
  sel.innerHTML = `<option value="">Select an agent…</option>` +
    agents.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');
  if (agents.find(a => a.id === current)) sel.value = current;
}

// ---------------------------------------------------------------------------
// Build Agent page
// ---------------------------------------------------------------------------

function renderTierOptions() {
  const el = document.getElementById('tierOptions');
  el.innerHTML = Object.entries(constructionTiers).map(([key, t]) => `
    <div class="strategy-option ${key === selectedTier ? 'selected' : ''}" data-tier-key="${key}">
      <b>${t.label}</b><span>${escapeHtml(t.description)}</span>
    </div>`).join('');
  el.querySelectorAll('[data-tier-key]').forEach(opt => {
    opt.addEventListener('click', () => {
      selectedTier = opt.dataset.tierKey;
      renderTierOptions();
      applyTierDisplay();
      updateJsonPreview();
    });
  });
}

function renderStrategyOptions() {
  const el = document.getElementById('strategyOptions');
  el.innerHTML = Object.entries(alignmentStrategies).map(([key, s]) => `
    <div class="strategy-option ${key === selectedStrategy ? 'selected' : ''}" data-key="${key}">
      <b>${s.label}</b><span>${escapeHtml(s.question)}</span>
    </div>`).join('');
  el.querySelectorAll('[data-key]').forEach(opt => {
    opt.addEventListener('click', () => {
      selectedStrategy = opt.dataset.key;
      renderStrategyOptions();
      updateJsonPreview();
    });
  });
}

function applyTierDisplay() {
  const isInterview = selectedTier === "interview";
  document.getElementById('groundedLabel').textContent = isInterview ? 'Interview material' : 'Grounded facts';
  document.getElementById('groundedNote').style.display = isInterview ? 'block' : 'none';
  document.getElementById('backgroundLabel').textContent = isInterview ? 'Interview transcript / notes' : 'Background';
  document.getElementById('f-background').style.minHeight = isInterview ? '130px' : '50px';
  document.getElementById('strategyLabel').textContent = 'Alignment strategy' + (isInterview ? ' (secondary)' : '');
  document.getElementById('strategyNote').textContent = isInterview
    ? "Optional — only fills gaps the interview material doesn't cover."
    : 'Each mitigates two of four uncertainty types and is structurally blind to the other two.';
  document.getElementById('identityLabel').textContent = 'Founder identity blend' + (isInterview ? ' (secondary)' : '');
  document.getElementById('identityNote').textContent = isInterview
    ? 'Optional — the interview material takes precedence if these conflict with it.'
    : 'Real founders score on more than one — set all three.';
  document.getElementById('dialsLabel').textContent = 'Assigned cognitive dials' + (isInterview ? ' (secondary)' : '');
}

function clearBuildForm() {
  editingAgentId = null;
  selectedTier = "trait";
  selectedStrategy = "visionary";
  ['name','age','gender','region','education','socioeconomic','background','expertise','outcomes','values','note'].forEach(k => {
    const el = document.getElementById('f-' + k);
    if (el) el.value = '';
  });
  ['missionary','darwinian','communitarian','risk','bias','dominance','optimism'].forEach(k => {
    document.getElementById('f-' + k).value = 5;
    document.getElementById('f-' + k + '-val').textContent = 5;
  });
  document.getElementById('f-temperature').value = 0.7;
  document.getElementById('f-temperature-val').textContent = 0.7;
  document.getElementById('bioPaste').value = '';
  document.getElementById('extractStatus').textContent = '';
  document.getElementById('deleteAgentBtn').style.display = 'none';
  document.getElementById('promptPreviewBlock').style.display = 'none';
  renderTierOptions();
  renderStrategyOptions();
  applyTierDisplay();
  updateJsonPreview();
}

function loadAgentIntoForm(agent) {
  editingAgentId = agent.id;
  selectedTier = agent.tier || 'trait';
  selectedStrategy = agent.alignment_strategy;
  document.getElementById('f-name').value = agent.name;
  document.getElementById('f-age').value = agent.demographics.age || '';
  document.getElementById('f-gender').value = agent.demographics.gender || '';
  document.getElementById('f-region').value = agent.demographics.region || '';
  document.getElementById('f-education').value = agent.demographics.education_level || '';
  document.getElementById('f-socioeconomic').value = agent.demographics.socioeconomic_background || '';
  document.getElementById('f-background').value = agent.grounded.background || '';
  document.getElementById('f-expertise').value = agent.grounded.expertise || '';
  document.getElementById('f-outcomes').value = agent.grounded.outcomes || '';
  document.getElementById('f-values').value = agent.grounded.values || '';
  document.getElementById('f-missionary').value = agent.founder_identity.missionary;
  document.getElementById('f-missionary-val').textContent = agent.founder_identity.missionary;
  document.getElementById('f-darwinian').value = agent.founder_identity.darwinian;
  document.getElementById('f-darwinian-val').textContent = agent.founder_identity.darwinian;
  document.getElementById('f-communitarian').value = agent.founder_identity.communitarian;
  document.getElementById('f-communitarian-val').textContent = agent.founder_identity.communitarian;
  document.getElementById('f-risk').value = agent.assigned.risk;
  document.getElementById('f-risk-val').textContent = agent.assigned.risk;
  document.getElementById('f-bias').value = agent.assigned.bias;
  document.getElementById('f-bias-val').textContent = agent.assigned.bias;
  document.getElementById('f-dominance').value = agent.assigned.dominance;
  document.getElementById('f-dominance-val').textContent = agent.assigned.dominance;
  document.getElementById('f-optimism').value = agent.assigned.optimism;
  document.getElementById('f-optimism-val').textContent = agent.assigned.optimism;
  document.getElementById('f-note').value = agent.assigned.note || '';
  document.getElementById('f-temperature').value = agent.temperature;
  document.getElementById('f-temperature-val').textContent = agent.temperature;
  document.getElementById('deleteAgentBtn').style.display = 'inline-block';
  document.getElementById('promptPreviewBlock').style.display = 'none';
  renderTierOptions();
  renderStrategyOptions();
  applyTierDisplay();
  updateJsonPreview();
  switchPage('build');
}

function currentFormPayload() {
  return {
    name: document.getElementById('f-name').value.trim(),
    tier: selectedTier,
    temperature: Number(document.getElementById('f-temperature').value),
    age: document.getElementById('f-age').value,
    gender: document.getElementById('f-gender').value.trim(),
    region: document.getElementById('f-region').value.trim(),
    education_level: document.getElementById('f-education').value.trim(),
    socioeconomic_background: document.getElementById('f-socioeconomic').value.trim(),
    background: document.getElementById('f-background').value.trim(),
    expertise: document.getElementById('f-expertise').value.trim(),
    outcomes: document.getElementById('f-outcomes').value.trim(),
    values: document.getElementById('f-values').value.trim(),
    alignment_strategy: selectedStrategy,
    missionary: Number(document.getElementById('f-missionary').value),
    darwinian: Number(document.getElementById('f-darwinian').value),
    communitarian: Number(document.getElementById('f-communitarian').value),
    risk: Number(document.getElementById('f-risk').value),
    bias: Number(document.getElementById('f-bias').value),
    dominance: Number(document.getElementById('f-dominance').value),
    optimism: Number(document.getElementById('f-optimism').value),
    note: document.getElementById('f-note').value.trim(),
  };
}

// ---- Live JSON preview, with light syntax highlighting ----
function jsonHighlight(obj) {
  const json = JSON.stringify(obj, null, 2);
  return escapeHtml(json)
    .replace(/(&quot;.*?&quot;)(:)/g, '<span class="jkey">$1</span>$2')
    .replace(/: (&quot;.*?&quot;)/g, ': <span class="jstr">$1</span>')
    .replace(/: (-?\d+\.?\d*)/g, ': <span class="jnum">$1</span>');
}

function buildPreviewObject() {
  const p = currentFormPayload();
  return {
    id: editingAgentId || "(not yet saved)",
    name: p.name,
    tier: p.tier,
    temperature: p.temperature,
    demographics: {
      age: p.age, gender: p.gender, region: p.region,
      education_level: p.education_level, socioeconomic_background: p.socioeconomic_background,
    },
    grounded: {
      background: p.background, expertise: p.expertise, outcomes: p.outcomes, values: p.values,
    },
    alignment_strategy: p.alignment_strategy,
    founder_identity: { missionary: p.missionary, darwinian: p.darwinian, communitarian: p.communitarian },
    assigned: { risk: p.risk, bias: p.bias, dominance: p.dominance, optimism: p.optimism, note: p.note },
  };
}

function updateJsonPreview() {
  const el = document.getElementById('jsonPreview');
  if (el) el.innerHTML = jsonHighlight(buildPreviewObject());
}

async function saveAgent() {
  const payload = currentFormPayload();
  if (!payload.name) { showToast("Give the agent a name first."); return; }
  try {
    let saved;
    if (editingAgentId) {
      saved = await api(`/api/agents/${editingAgentId}`, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      saved = await api('/api/agents', { method: 'POST', body: JSON.stringify(payload) });
    }
    editingAgentId = saved.id;
    document.getElementById('deleteAgentBtn').style.display = 'inline-block';
    if (saved.validation_warnings && saved.validation_warnings.length) {
      showToast(saved.validation_warnings[0]);
    } else {
      showToast("Saved.");
    }
    await loadAgents();
  } catch (e) {
    showToast("Couldn't save agent: " + e.message);
  }
}

async function deleteCurrentAgent() {
  if (!editingAgentId) return;
  if (!confirm("Delete this agent?")) return;
  try {
    await api(`/api/agents/${editingAgentId}`, { method: 'DELETE' });
    clearBuildForm();
    await loadAgents();
    showToast("Deleted.");
  } catch (e) {
    showToast("Couldn't delete agent.");
  }
}

async function previewPrompt() {
  const payload = currentFormPayload();
  if (!payload.name) { showToast("Give the agent a name first."); return; }
  try {
    const result = await api('/api/agents/preview-prompt', { method: 'POST', body: JSON.stringify(payload) });
    document.getElementById('promptPreviewText').textContent = result.prompt;
    document.getElementById('promptPreviewBlock').style.display = 'block';
    document.getElementById('promptPreviewBlock').classList.remove('collapsed');
  } catch (e) {
    showToast("Couldn't generate preview: " + e.message);
  }
}

async function extractBio() {
  const bio = document.getElementById('bioPaste').value.trim();
  if (!bio) { showToast("Paste some bio text first."); return; }
  const statusEl = document.getElementById('extractStatus');
  statusEl.textContent = "Extracting…";
  try {
    const fields = await api('/api/extract-bio', { method: 'POST', body: JSON.stringify({ bio }) });
    document.getElementById('f-background').value = fields.background || "";
    document.getElementById('f-expertise').value = fields.expertise || "";
    document.getElementById('f-outcomes').value = fields.outcomes || "";
    document.getElementById('f-values').value = fields.values || "";
    statusEl.textContent = "Filled in below.";
    updateJsonPreview();
  } catch (e) {
    statusEl.textContent = "";
    showToast("Couldn't extract fields from that text.");
  }
}

// ---------------------------------------------------------------------------
// Agent Library page
// ---------------------------------------------------------------------------

function renderLibrary() {
  const el = document.getElementById('libraryGrid');
  if (agents.length === 0) {
    el.innerHTML = `<p class="placeholder">No agents yet — build one on the Build Agent page.</p>`;
    return;
  }
  el.innerHTML = agents.map(a => {
    const strat = alignmentStrategies[a.alignment_strategy];
    const tier = constructionTiers[a.tier || 'trait'];
    return `
    <div class="library-card" style="border-left-color:${agentColor(a.name)};">
      <p class="name">${escapeHtml(a.name)}</p>
      <p class="tag">${escapeHtml(a.grounded.expertise || "no expertise noted")}</p>
      <div class="badge-row">
        <span class="badge">${tier ? tier.label : 'Tier 1'}</span>
        <span class="badge">${strat ? strat.label : a.alignment_strategy}</span>
        <span class="badge">${dominantIdentity(a.founder_identity)}-leaning</span>
        <span class="badge">temp ${a.temperature}</span>
      </div>
      <div class="card-actions">
        <button data-action="edit" data-id="${a.id}">edit</button>
        <button data-action="delete" data-id="${a.id}">delete</button>
      </div>
    </div>`;
  }).join('');

  el.querySelectorAll('[data-action="edit"]').forEach(btn => {
    btn.addEventListener('click', () => {
      const agent = agents.find(a => a.id === btn.dataset.id);
      if (agent) loadAgentIntoForm(agent);
    });
  });
  el.querySelectorAll('[data-action="delete"]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const agent = agents.find(a => a.id === btn.dataset.id);
      if (!confirm(`Delete ${agent ? agent.name : 'this agent'}?`)) return;
      try {
        await api(`/api/agents/${btn.dataset.id}`, { method: 'DELETE' });
        await loadAgents();
      } catch (e) {
        showToast("Couldn't delete agent.");
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Individual Reaction Elicitation page
// ---------------------------------------------------------------------------

async function runIndividual() {
  const scenario = document.getElementById('individualScenarioInput').value.trim();
  if (!scenario) { showToast("Describe a feedback stimulus first."); return; }
  const ids = selectedParticipantIds('individualParticipantPicker');
  if (ids.length === 0) { showToast("Select at least one agent."); return; }

  const selected = agents.filter(a => ids.includes(a.id));
  const btn = document.getElementById('runIndividualBtn');
  btn.disabled = true;
  const output = document.getElementById('individualOutput');
  output.innerHTML = `<div class="reaction-grid">` + selected.map(a => `
    <div class="reaction-card" id="reaction-${a.id}">
      <div class="who"><div class="avatar" style="background:${agentColor(a.name)}"></div><b>${escapeHtml(a.name)}</b></div>
      <div class="body loading-text">Thinking…</div>
    </div>`).join('') + `</div>`;

  try {
    const results = await api('/api/run/individual', { method: 'POST', body: JSON.stringify({ scenario, agent_ids: ids }) });
    results.forEach(r => {
      const card = document.getElementById('reaction-' + r.agent_id);
      if (r.error) {
        card.querySelector('.body').innerHTML = `<span class="error-text">Couldn't get a response for this agent.</span>`;
      } else {
        card.querySelector('.body').outerHTML = `
          <div class="body">
            <div class="field-label-sm">Reasoning (private)</div>
            <div class="reasoning-text">${escapeHtml(r.reasoning)}</div>
            <div class="field-label-sm">Stance</div>
            <div class="stance-text">${escapeHtml(r.stance)}</div>
          </div>`;
      }
    });
  } catch (e) {
    output.innerHTML = `<p class="error-text">Run failed: ${escapeHtml(e.message)}</p>`;
  }
  btn.disabled = false;
}

// ---------------------------------------------------------------------------
// Group Interaction Elicitation page
// ---------------------------------------------------------------------------

async function runGroup() {
  const scenario = document.getElementById('groupScenarioInput').value.trim();
  if (!scenario) { showToast("Describe a feedback stimulus first."); return; }
  const ids = selectedParticipantIds('groupParticipantPicker');
  if (ids.length < 2) { showToast("Select at least two agents for a group discussion."); return; }
  const rounds = Math.max(1, Math.min(4, Number(document.getElementById('roundsInput').value) || 2));

  const btn = document.getElementById('runGroupBtn');
  btn.disabled = true;
  const output = document.getElementById('groupOutput');
  output.innerHTML = `<p class="loading-text">Running the discussion — this can take a little while for multiple rounds…</p>`;

  try {
    const turns = await api('/api/run/group', { method: 'POST', body: JSON.stringify({ scenario, agent_ids: ids, rounds }) });
    output.innerHTML = `<div class="transcript">` + turns.map(t => `
      <div class="bubble">
        <div class="avatar" style="background:${agentColor(t.name)}; flex-shrink:0;"></div>
        <div class="msg">
          <div class="name">${escapeHtml(t.name)} <span style="font-weight:400; color:var(--ink-soft); font-size:11px;">round ${t.round}</span></div>
          <div>${escapeHtml(t.stance)}</div>
          ${t.reasoning ? `<details><summary>private reasoning</summary><div class="private-reasoning">${escapeHtml(t.reasoning)}</div></details>` : ''}
        </div>
      </div>`).join('') + `</div>`;
  } catch (e) {
    output.innerHTML = `<p class="error-text">Run failed: ${escapeHtml(e.message)}</p>`;
  }
  btn.disabled = false;
}

// ---------------------------------------------------------------------------
// Chat with Agent page
// ---------------------------------------------------------------------------

async function selectChatAgent(agentId) {
  chatAgentId = agentId || null;
  const input = document.getElementById('chatInput');
  const sendBtn = document.getElementById('chatSendBtn');
  const win = document.getElementById('chatWindow');
  if (!chatAgentId) {
    win.innerHTML = `<p class="placeholder">Pick an agent above to talk with them one-on-one.</p>`;
    input.disabled = true; sendBtn.disabled = true;
    return;
  }
  input.disabled = false; sendBtn.disabled = false;
  try {
    const history = await api(`/api/chat/${chatAgentId}`);
    renderChatWindow(history);
  } catch (e) {
    win.innerHTML = `<p class="error-text">Couldn't load chat history.</p>`;
  }
}

function renderChatWindow(history) {
  const win = document.getElementById('chatWindow');
  if (!history || history.length === 0) {
    win.innerHTML = `<p class="placeholder">No messages yet — say something below.</p>`;
    return;
  }
  win.innerHTML = history.map(m =>
    `<div class="chat-row ${m.role === 'user' ? 'user' : 'agent'}"><div class="msg">${escapeHtml(m.content)}</div></div>`
  ).join('');
  win.scrollTop = win.scrollHeight;
}

async function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text || !chatAgentId) return;

  const win = document.getElementById('chatWindow');
  const placeholder = win.querySelector('.placeholder');
  if (placeholder) win.innerHTML = "";

  const userRow = document.createElement('div');
  userRow.className = 'chat-row user';
  userRow.innerHTML = `<div class="msg">${escapeHtml(text)}</div>`;
  win.appendChild(userRow);
  input.value = "";

  const pending = document.createElement('div');
  pending.className = 'chat-row agent';
  pending.innerHTML = `<div class="msg loading-text">Thinking…</div>`;
  win.appendChild(pending);
  win.scrollTop = win.scrollHeight;

  try {
    const data = await api(`/api/chat/${chatAgentId}`, { method: 'POST', body: JSON.stringify({ message: text }) });
    pending.querySelector('.msg').classList.remove('loading-text');
    pending.querySelector('.msg').textContent = data.reply;
  } catch (e) {
    pending.querySelector('.msg').classList.remove('loading-text');
    pending.querySelector('.msg').classList.add('error-text');
    pending.querySelector('.msg').textContent = "Couldn't get a response.";
  }
  win.scrollTop = win.scrollHeight;
}

// ---------------------------------------------------------------------------
// Guidance page
// ---------------------------------------------------------------------------

function renderGuidance() {
  const stratEl = document.getElementById('guidanceStrategies');
  stratEl.innerHTML = Object.values(alignmentStrategies).map(s => `
    <div class="guidance-card" style="border-left-color:${'#A97527'}">
      <b>${escapeHtml(s.label)} — "${escapeHtml(s.question)}"</b>
      <p><b>Mitigates:</b> ${escapeHtml(s.mitigates)}</p>
      <p><b>Blind spot:</b> ${escapeHtml(s.blind_spot)}</p>
    </div>`).join('');

  const identEl = document.getElementById('guidanceIdentities');
  identEl.innerHTML = Object.entries(founderIdentityDescriptions).map(([key, desc]) => `
    <div class="guidance-card" style="border-left-color:${'#6B5CA5'}">
      <b>${key.charAt(0).toUpperCase() + key.slice(1)}</b>
      <p>${escapeHtml(desc)}</p>
    </div>`).join('');

  const tierEl = document.getElementById('guidanceTiers');
  tierEl.innerHTML = Object.values(constructionTiers).map(t => `
    <div class="guidance-card" style="border-left-color:${'#3F6E63'}">
      <b>${escapeHtml(t.label)}</b>
      <p>${escapeHtml(t.description)}</p>
    </div>`).join('');
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => switchPage(btn.dataset.page));
});

document.getElementById('newAgentBtn').addEventListener('click', clearBuildForm);
document.getElementById('libraryNewAgentBtn').addEventListener('click', () => { clearBuildForm(); switchPage('build'); });
document.getElementById('saveAgentBtn').addEventListener('click', saveAgent);
document.getElementById('deleteAgentBtn').addEventListener('click', deleteCurrentAgent);
document.getElementById('previewPromptBtn').addEventListener('click', previewPrompt);
document.getElementById('extractBioBtn').addEventListener('click', extractBio);
document.getElementById('promptPreviewToggle').addEventListener('click', () => {
  document.getElementById('promptPreviewBlock').classList.toggle('collapsed');
});

['name','age','gender','region','education','socioeconomic','background','expertise','outcomes','values','note'].forEach(k => {
  const el = document.getElementById('f-' + k);
  if (el) el.addEventListener('input', updateJsonPreview);
});
['missionary','darwinian','communitarian','risk','bias','dominance','optimism','temperature'].forEach(k => {
  const el = document.getElementById('f-' + k);
  el.addEventListener('input', (e) => {
    document.getElementById('f-' + k + '-val').textContent = e.target.value;
    updateJsonPreview();
  });
});

document.getElementById('runIndividualBtn').addEventListener('click', runIndividual);
document.getElementById('runGroupBtn').addEventListener('click', runGroup);

document.getElementById('chatAgentSelect').addEventListener('change', (e) => selectChatAgent(e.target.value));
document.getElementById('chatSendBtn').addEventListener('click', sendChatMessage);
document.getElementById('chatInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') sendChatMessage(); });
document.getElementById('clearChatBtn').addEventListener('click', async () => {
  if (!chatAgentId) return;
  try { await api(`/api/chat/${chatAgentId}/clear`, { method: 'POST' }); renderChatWindow([]); }
  catch (e) { showToast("Couldn't clear chat."); }
});

(async function init() {
  await loadReference();
  applyTierDisplay();
  updateJsonPreview();
  await loadAgents();
})();
