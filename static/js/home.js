const form = document.getElementById('check-form');
const input = document.getElementById('domain-input');
const btn = document.getElementById('submit-btn');
const formError = document.getElementById('form-error');
const loading = document.getElementById('loading');
const loadingDomain = document.getElementById('loading-domain');
const summaryEl = document.getElementById('summary');
const resultsEl = document.getElementById('results');

const DOMAIN_RE = /^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))+$/;

const STATUS_STYLES = {
  ok:   { label: 'OK',        cls: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  warn: { label: 'ADVERTENCIA', cls: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
  fail: { label: 'FALLA',     cls: 'bg-rose-500/10 text-rose-400 border-rose-500/30' },
  na:   { label: 'N/D',       cls: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/30' },
};

function badge(status) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.na;
  return `<span class="text-[10px] tracking-wider border rounded px-1.5 py-0.5 ${s.cls}">${s.label}</span>`;
}

function statusOf(section) {
  if (section === null || section === undefined) return 'na';
  if (typeof section === 'boolean') return section ? 'ok' : 'fail';
  if (typeof section === 'object') {
    if (section.error) return 'fail';
    if (section.valid === false) return 'fail';
    if (Array.isArray(section.warnings) && section.warnings.length > 0) return 'warn';
    return 'ok';
  }
  return 'na';
}

function esc(str) {
  return String(str).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function card(title, status, bodyHtml) {
  return `
    <div class="rise bg-zinc-900/50 border border-zinc-800 rounded-md p-4">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-xs tracking-[0.15em] text-zinc-400 uppercase">${title}</h3>
        ${badge(status)}
      </div>
      ${bodyHtml}
    </div>`;
}

function warningsList(warnings) {
  if (!Array.isArray(warnings) || warnings.length === 0) return '';
  return `<ul class="mt-2 space-y-1 text-[11px] text-amber-400/90 list-disc list-inside">
    ${warnings.map(w => `<li>${esc(w)}</li>`).join('')}
  </ul>`;
}

function recordBlock(record) {
  if (!record) return '';
  return `<pre class="record mt-2 overflow-x-auto text-[11px] text-zinc-300 bg-zinc-950 border border-zinc-800/80 rounded p-2.5">${esc(record)}</pre>`;
}

function kvGrid(obj, skip = []) {
  const entries = Object.entries(obj).filter(([k, v]) =>
    !skip.includes(k) && v !== null && v !== undefined && typeof v !== 'object'
  );
  if (entries.length === 0) return '';
  return `<div class="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] mt-2">
    ${entries.map(([k, v]) => `
      <span class="text-zinc-600">${esc(k)}</span>
      <span class="text-zinc-300 truncate">${esc(v)}</span>
    `).join('')}
  </div>`;
}

function flattenTagValue(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object' && !Array.isArray(v) && 'value' in v) return flattenTagValue(v.value);
  if (Array.isArray(v)) return v.map(flattenTagValue).join(', ');
  if (typeof v === 'object') {
    if (v.scheme && v.address) return `${v.scheme}:${v.address}`;
    return JSON.stringify(v);
  }
  return String(v);
}

function tagsGrid(tags) {
  if (!tags || typeof tags !== 'object') return '';
  const entries = Object.entries(tags);
  if (!entries.length) return '';
  return `<div class="grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] mt-2 pt-2 border-t border-zinc-800/60">
    ${entries.map(([k, v]) => `
      <span class="text-zinc-600">${esc(k)}</span>
      <span class="text-zinc-300 truncate">${esc(flattenTagValue(v))}</span>
    `).join('')}
  </div>`;
}

function policyGrid(policy) {
  if (!policy || typeof policy !== 'object') return '';
  const mx = Array.isArray(policy.mx)
    ? `<div class="flex flex-wrap gap-1.5 mt-2">${policy.mx.map(m => `<span class="text-[11px] bg-zinc-950 border border-zinc-800 rounded px-2 py-1 text-zinc-300">${esc(m)}</span>`).join('')}</div>`
    : '';
  return kvGrid(policy, ['mx']) + mx;
}

function renderRecordSection(title, section) {
  if (!section) return card(title, 'na', `<p class="text-[11px] text-zinc-600">sin datos</p>`);
  const status = statusOf(section);
  if (section.error) {
    return card(title, status, `<p class="text-[11px] text-rose-400">${esc(section.error)}</p>`);
  }
  let body = recordBlock(section.record);
  body += kvGrid(section, ['record', 'warnings', 'tags', 'policy', 'valid']);
  body += tagsGrid(section.tags);
  body += policyGrid(section.policy);
  body += warningsList(section.warnings);
  if (!body) {
    body = `<p class="text-[11px] text-zinc-600">sin registro publicado</p>`;
  }
  return card(title, status, body);
}

function renderDnssec(value) {
  const status = statusOf(value);
  const text = value ? 'DNSSEC activo y validado' : 'DNSSEC no está activo';
  return card('DNSSEC', status, `<p class="text-[11px] text-zinc-400">${text}</p>`);
}

function renderNs(section) {
  const status = statusOf(section);
  if (!section) return card('Nameservers', 'na', `<p class="text-[11px] text-zinc-600">sin datos</p>`);
  if (section.error) return card('Nameservers', status, `<p class="text-[11px] text-rose-400">${esc(section.error)}</p>`);
  const hosts = section.hostnames || [];
  const chips = hosts.map(h => `<span class="text-[11px] bg-zinc-950 border border-zinc-800 rounded px-2 py-1 text-zinc-300">${esc(h)}</span>`).join('');
  return card('Nameservers', status, `<div class="flex flex-wrap gap-1.5">${chips || '<span class="text-[11px] text-zinc-600">sin nameservers</span>'}</div>${warningsList(section.warnings)}`);
}

function renderMx(section) {
  const status = statusOf(section);
  if (!section) return card('MX', 'na', `<p class="text-[11px] text-zinc-600">sin datos</p>`);
  if (section.error) return card('MX', status, `<p class="text-[11px] text-rose-400">${esc(section.error)}</p>`);
  const hosts = section.hosts || [];
  const rows = hosts.map(h => {
    const pref = h.preference !== undefined ? h.preference : '—';
    const flags = Object.entries(h).filter(([k, v]) => typeof v === 'boolean');
    const flagHtml = flags.map(([k, v]) =>
      `<span class="text-[10px] px-1.5 py-0.5 rounded border ${v ? 'border-emerald-500/30 text-emerald-400' : 'border-zinc-700 text-zinc-600'}">${esc(k)}</span>`
    ).join(' ');
    return `<div class="flex items-center justify-between gap-2 py-1 border-b border-zinc-800/60 last:border-0">
      <span class="text-[11px] text-zinc-300 truncate">${esc(h.hostname || '?')} <span class="text-zinc-600">(prio ${esc(pref)})</span></span>
      <span class="flex gap-1 shrink-0">${flagHtml}</span>
    </div>`;
  }).join('');
  return card('MX', status, `<div class="mt-1">${rows || '<p class="text-[11px] text-zinc-600">sin registros MX</p>'}</div>${warningsList(section.warnings)}`);
}

function renderSoa(section) {
  const status = statusOf(section);
  if (!section || Object.keys(section).length === 0) return card('SOA', 'na', `<p class="text-[11px] text-zinc-600">sin datos</p>`);
  if (section.error) return card('SOA', status, `<p class="text-[11px] text-rose-400">${esc(section.error)}</p>`);
  const body = recordBlock(section.record) + kvGrid(section.values || {});
  return card('SOA', status, body || `<p class="text-[11px] text-zinc-600">sin datos</p>`);
}

function statusOfDkim(entries) {
  if (!Array.isArray(entries) || entries.length === 0) return 'na';
  const found = entries.filter(e => e.found);
  if (found.some(e => e.valid === false)) return 'fail';
  if (found.some(e => e.valid === true)) return 'ok';
  return 'warn';
}

function renderDkim(entries) {
  const status = statusOfDkim(entries);
  if (!Array.isArray(entries) || entries.length === 0) {
    return card('DKIM', 'na', `<p class="text-[11px] text-zinc-600">sin datos</p>`);
  }

  const found = entries.filter(e => e.found);
  const notFound = entries.filter(e => !e.found);

  let body = '';
  if (found.length) {
    body += found.map(e => `
      <div class="py-1.5 border-b border-zinc-800/60 last:border-0">
        <div class="flex items-center justify-between gap-2">
          <span class="text-[11px] text-zinc-300">${esc(e.selector)}._domainkey</span>
          <span class="text-[10px] px-1.5 py-0.5 rounded border ${e.valid ? 'border-emerald-500/30 text-emerald-400' : 'border-rose-500/30 text-rose-400'}">
            ${e.valid ? esc(`${e.key_type || ''} ${e.key_size || ''}`.trim()) : 'inválido'}
          </span>
        </div>
        ${e.error ? `<p class="text-[11px] text-rose-400 mt-1">${esc(e.error)}</p>` : ''}
        ${e.record ? recordBlock(e.record) : ''}
      </div>
    `).join('');
  } else {
    body += `<p class="text-[11px] text-zinc-500 leading-relaxed">Ningún selector común publica un registro DKIM. El dominio podría usar un selector personalizado fuera de este análisis.</p>`;
  }

  if (notFound.length) {
    body += `<p class="text-[10px] text-zinc-700 mt-2">selectores probados sin resultado: ${notFound.map(e => esc(e.selector)).join(', ')}</p>`;
  }

  return card('DKIM', status, body);
}

function computeSummary(data) {
  const sections = ['spf', 'dmarc', 'mx', 'mta_sts', 'smtp_tls_reporting', 'bimi', 'ns'];
  let ok = 0, warn = 0, fail = 0;
  sections.forEach(k => {
    const s = statusOf(data[k]);
    if (s === 'ok') ok++; else if (s === 'warn') warn++; else if (s === 'fail') fail++;
  });
  if (statusOf(data.dnssec) === 'ok') ok++; else fail++;
  const dkimStatus = statusOfDkim(data.dkim);
  if (dkimStatus === 'ok') ok++; else if (dkimStatus === 'warn') warn++; else if (dkimStatus === 'fail') fail++;
  return { ok, warn, fail };
}

function render(domain, data) {
  const { ok, warn, fail } = computeSummary(data);
  summaryEl.classList.remove('hidden');
  summaryEl.innerHTML = `
    <div class="flex flex-wrap items-center gap-4 text-xs border border-zinc-800 rounded-md px-4 py-3 bg-zinc-900/40">
      <span class="text-zinc-200">${esc(data.domain || domain)}</span>
      <span class="text-zinc-700">/</span>
      <span class="text-zinc-500">${esc(data.base_domain || '')}</span>
      <span class="ml-auto flex items-center gap-3">
        <span class="text-emerald-400">${ok} ok</span>
        <span class="text-amber-400">${warn} advertencias</span>
        <span class="text-rose-400">${fail} fallas</span>
      </span>
    </div>`;

  resultsEl.innerHTML = [
    renderDnssec(data.dnssec),
    renderRecordSection('SPF', data.spf),
    renderRecordSection('DMARC', data.dmarc),
    renderDkim(data.dkim),
    renderMx(data.mx),
    renderRecordSection('MTA-STS', data.mta_sts),
    renderRecordSection('TLS-RPT', data.smtp_tls_reporting),
    renderRecordSection('BIMI', data.bimi),
    renderNs(data.ns),
    renderSoa(data.soa),
  ].join('');
}

async function runCheck(domain) {
  formError.classList.add('hidden');
  summaryEl.classList.add('hidden');
  resultsEl.innerHTML = '';
  loadingDomain.textContent = domain;
  loading.classList.remove('hidden');
  btn.disabled = true;

  try {
    const res = await fetch(`/api/check/${encodeURIComponent(domain)}`);
    if (!res.ok) throw new Error(`el servicio respondió ${res.status}`);
    const data = await res.json();
    render(domain, data);
    const url = new URL(window.location);
    url.searchParams.set('domain', domain);
    window.history.replaceState({}, '', url);
  } catch (err) {
    formError.textContent = `No se pudo completar el análisis: ${err.message}`;
    formError.classList.remove('hidden');
  } finally {
    loading.classList.add('hidden');
    btn.disabled = false;
  }
}

form.addEventListener('submit', (e) => {
  e.preventDefault();
  const domain = input.value.trim().toLowerCase();
  if (!DOMAIN_RE.test(domain)) {
    formError.textContent = 'Ingresa un dominio válido, por ejemplo: tudominio.com';
    formError.classList.remove('hidden');
    return;
  }
  runCheck(domain);
});

const preset = new URL(window.location).searchParams.get('domain');
if (preset) {
  input.value = preset;
  if (DOMAIN_RE.test(preset)) runCheck(preset);
}
