// Founder Cognition Lab -- client-side logic. Talks only to the local Flask
// API at /api/... ; the Anthropic key never touches the browser.

let agents = [];
let selectedAgentId = null;   // null = "new agent" mode
let chatAgentId = null;
let alignmentStrategies = {};
let selectedStrategy = "visionary";

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

// ---------- Load ----------
async function loadReference() {
  try {
    const ref = await api('/api/reference');
    alignmentStrategies = ref.alignment_strategies;
  } catch (e) {
    showToast("Couldn't load reference data from the server.");
  }
}

async function loadAgents(keepSelection) {
  try {
    agents = await api('/api/agents');
  } catch (e) {
    agents = [];
    showToast("Couldn't load agents from the server.");
  }
  renderRosterStrip();
  renderParticipantPicker();
  renderChatAgentSelect();
  if (!keepSelection) {
    selectedAgentId = null;
    renderAgentPanel();
  }
}

// ---------- Roster strip (top of sidebar) ----------
function renderRosterStrip() {
  const el = document.getElementById('rosterStrip');
  if (agents.length === 0) {
    el.innerHTML = `<p class="placeholder-small">No agents yet — create one below.</p>`;
    return;
  }
  el.innerHTML = agents.map(a => `
    <div class="roster-chip ${a.id === selectedAgentId ? 'selected' : ''}" data-id="${a.id}">
      <span class="dot" style="background:${agentColor(a.name)}"></span>${escapeHtml(a.name)}
    </div>`).join('');
  el.querySelectorAll('.roster-chip').forEach(chip => {
    chip.addEventListener('click', () => selectAgent(chip.dataset.id));
  });
}

function renderParticipantPicker() {
  const el = document.getElementById('participantPicker');
  if (agents.length === 0) { el.innerHTML = `<span class="placeholder-small">Create an agent first.</span>`; return; }
  el.innerHTML = agents.map(a =>
    `<label><input type="checkbox" class="participant-cb" value="${a.id}" checked /> ${escapeHtml(a.name)}</label>`
  ).join('');
}

function renderChatAgentSelect() {
  const sel = document.getElementById('chatAgentSelect');
  const current = sel.value;
  sel.innerHTML = `<option value="">Select an agent…</option>` +
    agents.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');
  if (agents.find(a => a.id === current)) sel.value = current;
}

function selectedParticipantIds() {
  return Array.from(document.querySelectorAll('.participant-cb:checked')).map(cb => cb.value);
}

// ---------- Agent settings panel (the vertical bar, replaces the old modal) ----------
function selectAgent(agentId) {
  selectedAgentId = agentId;
  renderRosterStrip();
  renderAgentPanel();
}

function newAgentClicked() {
  selectedAgentId = null;
  renderRosterStrip();
  renderAgentPanel();
}

function renderAgentPanel() {
  const agent = selectedAgentId ? agents.find(a => a.id === selectedAgentId) : null;
  const d = agent ? agent.demographics : { age: "", gender: "", region: "", education_level: "", socioeconomic_background: "" };
  const g = agent ? agent.grounded : { background: "", expertise: "", outcomes: "", values: "" };
  const fi = agent ? agent.founder_identity : { missionary: 5, darwinian: 5, communitarian: 5 };
  const asn = agent ? agent.assigned : { risk: 5, bias: 5, dominance: 5, optimism: 5, note: "" };
  selectedStrategy = agent ? agent.alignment_strategy : "visionary";

  const strategyHtml = Object.entries(alignmentStrategies).map(([key, s]) => `
    <div class="strategy-option ${key === selectedStrategy ? 'selected' : ''}" data-key="${key}">
      <b>${s.label}</b><span>${escapeHtml(s.question)}</span>
    </div>`).join('');

  const el = document.getElementById('agentPanel');
  el.innerHTML = `
    <div class="panel-section">
      <div class="panel-label">${agent ? 'Edit agent' : 'New agent'}</div>
      <div class="bio-box">
        <label style="font-size:11px; color:var(--ink-soft); display:block; margin-bottom:4px;">Optional: paste a bio to pre-fill grounded fields below</label>
        <textarea id="bioPaste" placeholder="Paste raw bio / profile text…"></textarea>
        <button class="btn btn-ghost" id="extractBioBtn">Extract grounded fields</button>
        <span id="extractStatus" style="font-size:11px; color:var(--ink-soft); margin-left:6px;"></span>
      </div>
      <div class="field"><label for="f-name">Name</label><input type="text" id="f-name" value="${escapeHtml(agent ? agent.name : '')}" placeholder="e.g. Priya Nandan" /></div>
    </div>

    <div class="panel-section">
      <div class="panel-label">Demographics</div>
      <div class="panel-note">Baseline for every agent, so a roster doesn't default to one implicit "typical founder."</div>
      <div class="field-row">
        <div class="field"><label for="f-age">Age</label><input type="number" id="f-age" value="${escapeHtml(String(d.age || ''))}" /></div>
        <div class="field"><label for="f-gender">Gender</label><input type="text" id="f-gender" value="${escapeHtml(d.gender || '')}" /></div>
      </div>
      <div class="field-row">
        <div class="field"><label for="f-region">Region</label><input type="text" id="f-region" value="${escapeHtml(d.region || '')}" /></div>
        <div class="field"><label for="f-education">Education</label><input type="text" id="f-education" value="${escapeHtml(d.education_level || '')}" /></div>
      </div>
      <div class="field"><label for="f-socioeconomic">Socioeconomic background</label><input type="text" id="f-socioeconomic" value="${escapeHtml(d.socioeconomic_background || '')}" /></div>
    </div>

    <div class="panel-section">
      <div class="panel-label">Grounded facts</div>
      <div class="field"><label for="f-background">Background</label><textarea id="f-background">${escapeHtml(g.background || '')}</textarea></div>
      <div class="field"><label for="f-expertise">Domain expertise</label><input type="text" id="f-expertise" value="${escapeHtml(g.expertise || '')}" /></div>
      <div class="field"><label for="f-outcomes">Prior outcomes</label><input type="text" id="f-outcomes" value="${escapeHtml(g.outcomes || '')}" /></div>
      <div class="field"><label for="f-values">Stated values / voice</label><textarea id="f-values">${escapeHtml(g.values || '')}</textarea></div>
    </div>

    <div class="panel-section">
      <div class="panel-label">Alignment strategy</div>
      <div class="panel-note">Each mitigates two of four uncertainty types and is structurally blind to the other two.</div>
      <div class="strategy-options" id="strategyOptions">${strategyHtml}</div>
    </div>

    <div class="panel-section">
      <div class="panel-label">Founder identity blend</div>
      <div class="panel-note">Real founders score on more than one — set all three.</div>
      <div class="slider-row"><label>Missionary</label><input type="range" id="f-missionary" min="0" max="10" value="${fi.missionary}" /><span class="val" id="f-missionary-val">${fi.missionary}</span></div>
      <div class="slider-row"><label>Darwinian</label><input type="range" id="f-darwinian" min="0" max="10" value="${fi.darwinian}" /><span class="val" id="f-darwinian-val">${fi.darwinian}</span></div>
      <div class="slider-row"><label>Communitarian</label><input type="range" id="f-communitarian" min="0" max="10" value="${fi.communitarian}" /><span class="val" id="f-communitarian-val">${fi.communitarian}</span></div>
    </div>

    <div class="panel-section">
      <div class="panel-label">Assigned cognitive dials</div>
      <div class="panel-note">Experimental variables you set — not psychology read off a resume.</div>
      <div class="slider-row"><label>Risk tolerance</label><input type="range" id="f-risk" min="0" max="10" value="${asn.risk}" /><span class="val" id="f-risk-val">${asn.risk}</span></div>
      <div class="slider-row"><label>Confirmation bias</label><input type="range" id="f-bias" min="0" max="10" value="${asn.bias}" /><span class="val" id="f-bias-val">${asn.bias}</span></div>
      <div class="slider-row"><label>Group dominance</label><input type="range" id="f-dominance" min="0" max="10" value="${asn.dominance}" /><span class="val" id="f-dominance-val">${asn.dominance}</span></div>
      <div class="slider-row"><label>Optimism</label><input type="range" id="f-optimism" min="0" max="10" value="${asn.optimism}" /><span class="val" id="f-optimism-val">${asn.optimism}</span></div>
      <div class="field"><label for="f-note">Note (optional)</label><input type="text" id="f-note" value="${escapeHtml(asn.note || '')}" /></div>
    </div>

    <div class="panel-actions">
      <button class="btn btn-primary" id="saveAgentBtn" style="flex:2;">${agent ? 'Save changes' : 'Create agent'}</button>
      ${agent ? '<button class="btn btn-danger" id="deleteAgentBtn">Delete</button>' : ''}
    </div>

    ${agent ? `
    <div class="panel-section" style="margin-top:22px;">
      <div class="panel-label">Memory stream</div>
      <div class="panel-note">Every scenario reaction is logged here automatically. Highlighted entries are reflections this agent synthesized from its own recent memories.</div>
      <div class="memory-feed" id="memoryFeed"><p class="placeholder-small">Loading…</p></div>
    </div>` : ''}
  `;

  // wire up strategy picker
  el.querySelectorAll('.strategy-option').forEach(opt => {
    opt.addEventListener('click', () => {
      selectedStrategy = opt.dataset.key;
      el.querySelectorAll('.strategy-option').forEach(o => o.classList.toggle('selected', o === opt));
    });
  });
  // wire up sliders
  ['missionary','darwinian','communitarian','risk','bias','dominance','optimism'].forEach(k => {
    const input = document.getElementById('f-' + k);
    if (input) input.addEventListener('input', (e) => {
      document.getElementById('f-' + k + '-val').textContent = e.target.value;
    });
  });
  document.getElementById('extractBioBtn').addEventListener('click', extractBio);
  document.getElementById('saveAgentBtn').addEventListener('click', saveAgentFromPanel);
  const delBtn = document.getElementById('deleteAgentBtn');
  if (delBtn) delBtn.addEventListener('click', deleteSelectedAgent);

  if (agent) loadMemoryFeed(agent.id);
}

async function saveAgentFromPanel() {
  const name = document.getElementById('f-name').value.trim();
  if (!name) { showToast("Give the agent a name first."); return; }

  const payload = {
    name: name,
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
    note: document.getElementById('f-note').value.trim()
  };

  try {
    let saved;
    if (selectedAgentId) {
      saved = await api(`/api/agents/${selectedAgentId}`, { method: 'PUT', body: JSON.stringify(payload) });
    } else {
      saved = await api('/api/agents', { method: 'POST', body: JSON.stringify(payload) });
    }
    selectedAgentId = saved.id;
    await loadAgents(true);
    renderAgentPanel();
    showToast(selectedAgentId ? "Saved." : "Created.");
  } catch (e) {
    showToast("Couldn't save agent: " + e.message);
  }
}

async function deleteSelectedAgent() {
  if (!selectedAgentId) return;
  const agent = agents.find(a => a.id === selectedAgentId);
  if (!confirm(`Delete ${agent ? agent.name : 'this agent'}?`)) return;
  try {
    await api(`/api/agents/${selectedAgentId}`, { method: 'DELETE' });
    selectedAgentId = null;
    await loadAgents(true);
    renderAgentPanel();
  } catch (e) {
    showToast("Couldn't delete agent.");
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
  } catch (e) {
    statusEl.textContent = "";
    showToast("Couldn't extract fields from that text.");
  }
}

async function loadMemoryFeed(agentId) {
  const el = document.getElementById('memoryFeed');
  if (!el) return;
  try {
    const memory = await api(`/api/agents/${agentId}/memory`);
    if (memory.length === 0) {
      el.innerHTML = `<p class="placeholder-small">No memories yet — run a scenario with this agent.</p>`;
      return;
    }
    el.innerHTML = memory.slice().reverse().map(m => `
      <div class="memory-item ${m.type === 'reflection' ? 'reflection' : ''}">
        <div class="meta"><span class="badge">${escapeHtml(m.type)}</span><span class="badge">importance ${m.importance}/10</span></div>
        <div>${escapeHtml(m.text)}</div>
      </div>`).join('');
  } catch (e) {
    el.innerHTML = `<p class="error-text">Couldn't load memory.</p>`;
  }
}

// ---------- Tabs ----------
function switchTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === tab));
  document.getElementById('panel-individual').style.display = tab === 'individual' ? 'block' : 'none';
  document.getElementById('panel-group').style.display = tab === 'group' ? 'block' : 'none';
  document.getElementById('panel-chat').style.display = tab === 'chat' ? 'block' : 'none';
}

// ---------- Individual run ----------
async function runIndividual() {
  const scenario = document.getElementById('scenarioInput').value.trim();
  if (!scenario) { showToast("Describe a feedback stimulus first."); return; }
  const ids = selectedParticipantIds();
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
  if (selectedAgentId) loadMemoryFeed(selectedAgentId); // refresh memory if the panel is open on one of the runners
}

// ---------- Group run ----------
async function runGroup() {
  const scenario = document.getElementById('scenarioInput').value.trim();
  if (!scenario) { showToast("Describe a feedback stimulus first."); return; }
  const ids = selectedParticipantIds();
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
  if (selectedAgentId) loadMemoryFeed(selectedAgentId);
}

// ---------- Chat ----------
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

// ---------- Wiring ----------
document.getElementById('newAgentBtn').addEventListener('click', newAgentClicked);

document.querySelectorAll('.tab').forEach(t => {
  t.addEventListener('click', () => switchTab(t.dataset.tab));
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
  await loadAgents();
})();
