/* util.js — helpers de página partilhados pelas áreas novas (conjunto, dados,
   modelo, desenho, laboratório). features.js, paralelos.js e planta.js mantêm
   cópias próprias, para não mudarem de comportamento. */
(function () {
  'use strict';
  const V = window.VENKO = window.VENKO || {};

  const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (t) => String(t).replace(/[&<>"']/g, (c) => ESC[c]);
  const num = (v, d) => (v == null ? '–'
    : v.toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d }));
  const sinal = (v, d = 3) => (v == null ? '–' : (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v), d));
  const pct = (v) => Math.round(v * 100) + '%';
  const cssv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const icone = (id, cls = 'icon') => `<svg class="${cls}" aria-hidden="true"><use href="#${id}"/></svg>`;

  async function pedir(url, opts) {
    const r = await fetch(url, opts);
    const corpo = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof corpo.detail === 'string' ? corpo.detail : `HTTP ${r.status}`);
    return corpo;
  }
  const post = (url, corpo) => pedir(url, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corpo) });

  const gate = (sev, titulo, msg, extra = '') => `<div class="gate ${sev}">
    ${icone(sev === 'good' ? 'i-check' : 'i-alert')}
    <div style="flex:1"><div class="gate-title">${titulo}</div><div class="gate-msg">${msg}</div>${extra}</div></div>`;

  const ALVOS = [['speedtest_down_mbps', 'Download', 'Mbps'], ['speedtest_up_mbps', 'Upload', 'Mbps'],
    ['latency_ms', 'Latência', 'ms'], ['jitter_ms', 'Jitter', 'ms']];
  const ALVO = Object.fromEntries(ALVOS.map(([k, r, u]) => [k, { rotulo: r, unidade: u }]));

  // Como a produção obtém a coluna pelo TR-181 (core/features.STATUS_TR181).
  const STATUS_TR181 = { padrao: ['ok', 'TR-181 padrão'], derivavel: ['ok', 'derivável do TR-181'],
    proxy: ['mid', 'proxy TR-181'], extensao: ['mid', 'extensão de fabricante'],
    ausente: ['lab', 'sem caminho TR-069'], desconhecido: ['leak', 'TR-181 não classificado'] };
  const NIVEL = { '100%': ['ok', '100% TR-069'], proxy: ['mid', 'TR-069 com proxy'], parcial: ['lab', 'TR-069 parcial'] };
  const tagTr181 = (t) => {
    const [cls, rot] = STATUS_TR181[(t || {}).status] || STATUS_TR181.desconhecido;
    return `<span class="tag ${cls}" title="${esc([(t || {}).caminho, (t || {}).nota].filter(Boolean).join(' · '))}">${rot}</span>`;
  };
  const tagNivel = (cob) => {
    if (!cob) return '';
    const [cls, rot] = NIVEL[cob.nivel] || NIVEL.parcial;
    return `<span class="tag ${cls}">${rot}</span>`;
  };
  const tagLacuna = (l) => {
    const [cls, rot] = STATUS_TR181[l.status] || STATUS_TR181.desconhecido;
    return `<span class="tag ${cls}" title="${esc([rot, l.caminho, l.nota].filter(Boolean).join(' · '))}">${esc(l.feature)}</span>`;
  };

  // Redesenhar com innerHTML apaga o foco, o cursor e os <details> abertos. Isto devolve
  // os três, achando o elemento de novo pelo id ou pelo data-k.
  function seletorDe(el) {
    if (!el || el === document.body) return null;
    if (el.id) return '#' + CSS.escape(el.id);
    if (el.dataset && el.dataset.k) return `[data-k="${CSS.escape(el.dataset.k)}"]`;
    return null;
  }
  function redesenhar(host, html) {
    const el = document.activeElement;
    const sel = host.contains(el) ? seletorDe(el) : null;
    const ini = sel && typeof el.selectionStart === 'number' ? el.selectionStart : null;
    const fim = sel && typeof el.selectionEnd === 'number' ? el.selectionEnd : null;
    const abertos = new Set([...host.querySelectorAll('details[data-k]')].filter((d) => d.open).map((d) => d.dataset.k));
    host.innerHTML = html;
    host.querySelectorAll('details[data-k]').forEach((d) => { if (abertos.has(d.dataset.k)) d.open = true; });
    if (!sel) return;
    const novo = host.querySelector(sel);
    if (!novo) return;
    novo.focus();
    if (ini != null) {
      try { novo.setSelectionRange(ini, fim); } catch (e) { /* select e checkbox não têm cursor */ }
    }
  }

  V.util = { esc, num, sinal, pct, cssv, icone, pedir, post, gate, ALVOS, ALVO, STATUS_TR181,
             tagTr181, tagNivel, tagLacuna, redesenhar };
})();
