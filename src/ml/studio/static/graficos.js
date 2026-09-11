/* =====================================================================
   graficos.js — nucleo puro de desenho em canvas do QoE Studio.

   Nao le estado global e nao toca no DOM alem do canvas que recebe.
   Cada funcao devolve os alvos de hit-test para a camada de tooltip,
   entao o desenho e o hover ficam separados. Carregado ANTES de
   studio.js, que consome tudo pelo namespace window.VENKO.
   ===================================================================== */
window.VENKO = window.VENKO || {};

(function () {
  'use strict';

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  /* Canvas em HiDPI: sem isto o texto sai borrado em tela retina. */
  function prepare(canvas, height) {
    const ratio = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    canvas.height = height * ratio;
    canvas.width = width * ratio;
    canvas.style.height = height + 'px';
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    return { ctx, width, height };
  }

  function niceTicks(min, max, count) {
    const span = (max - min) || 1;
    const raw = span / count;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].find((m) => m * mag >= raw) * mag;
    const out = [];
    for (let v = Math.floor(min / step) * step; v <= max + 1e-9; v += step) out.push(v);
    return out;
  }

  function axes(ctx, box, ticks, yFmt, xLabels) {
    ctx.strokeStyle = css('--grid');
    ctx.lineWidth = 1;
    ctx.fillStyle = css('--ink-muted');
    ctx.font = '11px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    ticks.forEach((t) => {
      const y = box.y(t);
      // Meia-pixel: uma hairline em coordenada inteira vira 2px borrados.
      ctx.beginPath();
      ctx.moveTo(box.l, Math.round(y) + 0.5);
      ctx.lineTo(box.l + box.w, Math.round(y) + 0.5);
      ctx.stroke();
      ctx.fillText(yFmt(t), box.l - 8, y);
    });
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    xLabels.forEach((label, i) => ctx.fillText(label.text, label.x, box.t + box.h + 9));
  }

  /* ---------- linhas: contencao (dispositivos no X) ---------- */
  VENKO.drawLines = function (canvas, spec) {
    const { ctx, width, height } = prepare(canvas, spec.height || 300);
    const box = { l: 62, t: 14, w: width - 62 - 104, h: (spec.height || 300) - 14 - 30 };
    box.y = (v) => box.t + box.h - ((v - lo) / (hi - lo)) * box.h;
    const all = spec.series.flatMap((s) => s.points.map((p) => p.v)).filter((v) => v != null);
    let lo = 0;
    let hi = Math.max(...all) * 1.12 || 1;
    const ticks = niceTicks(lo, hi, 4);
    hi = Math.max(hi, ticks[ticks.length - 1]);

    const xs = spec.x.map((_, i) =>
      box.l + (spec.x.length === 1 ? box.w / 2 : (i / (spec.x.length - 1)) * box.w));
    axes(ctx, box, ticks, spec.yFmt || String,
      spec.x.map((t, i) => ({ text: t, x: xs[i] })));

    const hits = [];
    const endLabels = [];
    spec.series.forEach((s) => {
      ctx.strokeStyle = s.color;
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.beginPath();
      let started = false;
      s.points.forEach((p, i) => {
        if (p.v == null) return;
        const X = xs[i];
        const Y = box.y(p.v);
        started ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
        started = true;
      });
      ctx.stroke();
      s.points.forEach((p, i) => {
        if (p.v == null) return;
        const X = xs[i];
        const Y = box.y(p.v);
        // Anel de 2px na cor da superficie: separa marcas sobrepostas.
        ctx.beginPath(); ctx.arc(X, Y, 5.5, 0, Math.PI * 2);
        ctx.fillStyle = css('--surface-1'); ctx.fill();
        ctx.beginPath(); ctx.arc(X, Y, 4, 0, Math.PI * 2);
        ctx.fillStyle = s.color; ctx.fill();
        hits.push({ x: X, y: Y, r: 12, label: s.label, value: p.v, at: spec.x[i], color: s.color });
      });
      // Rotulo direto no fim da linha: no modo claro, cor sozinha nao basta
      // pra distinguir as series. Desenhados depois, juntos, para poderem
      // ser afastados entre si.
      const last = [...s.points].map((p, i) => ({ p, i })).reverse().find((e) => e.p.v != null);
      if (last) endLabels.push({ text: s.label, x: xs[last.i] + 10, y: box.y(last.p.v), color: s.color });
    });

    // Duas linhas que terminam quase juntas sobrescreveriam os rotulos uma da
    // outra. Empurra na vertical preservando a ordem, dentro da area do grafico.
    const GAP = 13;
    endLabels.sort((a, b) => a.y - b.y);
    for (let i = 1; i < endLabels.length; i++) {
      if (endLabels[i].y - endLabels[i - 1].y < GAP) endLabels[i].y = endLabels[i - 1].y + GAP;
    }
    const overflow = endLabels.length ? endLabels[endLabels.length - 1].y - (box.t + box.h) : 0;
    if (overflow > 0) endLabels.forEach((l) => { l.y -= overflow; });
    ctx.font = '11.5px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'middle';
    endLabels.forEach((l) => {
      ctx.fillStyle = css('--ink-2');
      ctx.fillText(l.text, l.x + 9, l.y);
      // Ponto na cor da serie ao lado do texto: identidade sem tingir o texto.
      ctx.beginPath(); ctx.arc(l.x + 3, l.y, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = l.color; ctx.fill();
    });

    // Titulo do eixo Y: a unidade aparece uma vez, nao repetida na legenda.
    if (spec.yTitle) {
      ctx.save();
      ctx.translate(13, box.t + box.h / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.fillStyle = css('--ink-muted');
      ctx.font = '11px system-ui, -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(spec.yTitle, 0, 0);
      ctx.restore();
    }
    return hits;
  };

  /* ---------- barras agrupadas: restricao dominante ---------- */
  VENKO.drawGroupedBars = function (canvas, spec) {
    const H = spec.height || 300;
    const { ctx, width } = prepare(canvas, H);
    const box = { l: 54, t: 14, w: width - 66, h: H - 14 - 34 };
    const hi = Math.max(spec.max || 100, 1);
    box.y = (v) => box.t + box.h - (v / hi) * box.h;
    const ticks = niceTicks(0, hi, 4);
    const groupW = box.w / spec.groups.length;
    axes(ctx, box, ticks, spec.yFmt || String,
      spec.groups.map((g, i) => ({ text: g.label, x: box.l + groupW * (i + 0.5) })));

    const hits = [];
    const n = spec.series.length;
    const barW = Math.min(34, (groupW - 26) / n);
    spec.groups.forEach((g, gi) => {
      const start = box.l + groupW * gi + (groupW - (barW * n + 2 * (n - 1))) / 2;
      spec.series.forEach((s, si) => {
        const v = g.values[si];
        if (v == null) return;
        const x = start + si * (barW + 2);   // 2px de folga entre barras
        const y = box.y(v);
        const h = box.t + box.h - y;
        ctx.fillStyle = s.color;
        ctx.beginPath();
        // ponta arredondada, base ancorada na linha zero
        ctx.roundRect(x, y, barW, Math.max(h, 1.5), [4, 4, 0, 0]);
        ctx.fill();
        hits.push({ x: x + barW / 2, y, r: 14, label: s.label, value: v, at: g.label, color: s.color });
      });
    });
    return hits;
  };

  /* ---------- planta baixa: pontos medidos, sem interpolacao ---------- */
  VENKO.drawFloorPlan = function (canvas, spec) {
    const H = spec.height || 340;
    const { ctx, width } = prepare(canvas, H);
    // Folga suficiente para o raio da maior marca nao vazar o retangulo.
    const pad = 34;
    // O envelope vem em cm; preserva a proporcao real do comodo.
    const scale = Math.min((width - pad * 2) / spec.envelope.w, (H - pad * 2) / spec.envelope.h);
    const ox = (width - spec.envelope.w * scale) / 2;
    const oy = (H - spec.envelope.h * scale) / 2;
    const px = (x) => ox + x * scale;
    const py = (y) => oy + y * scale;

    ctx.strokeStyle = css('--axis');
    ctx.lineWidth = 1.5;
    ctx.strokeRect(px(0), py(0), spec.envelope.w * scale, spec.envelope.h * scale);

    ctx.fillStyle = css('--ink-muted');
    ctx.font = '10.5px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${spec.envelope.w} cm`, px(spec.envelope.w / 2), py(0) - 12);
    ctx.save();
    ctx.translate(px(0) - 13, py(spec.envelope.h / 2));
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`${spec.envelope.h} cm`, 0, 0);
    ctx.restore();

    // Roteador: marca de identidade, nunca uma cor de serie.
    const rx = px(spec.envelope.routerX);
    const ry = py(spec.envelope.routerY);
    ctx.strokeStyle = css('--ink-2');
    ctx.lineWidth = 1.6;
    ctx.beginPath(); ctx.arc(rx, ry, 5, 0, Math.PI * 2); ctx.stroke();
    [9, 13].forEach((r) => {
      ctx.beginPath();
      ctx.arc(rx, ry, r, -Math.PI * 0.85, -Math.PI * 0.15);
      ctx.stroke();
    });
    // Rotulo abaixo do icone com halo da superficie: o roteador fica junto da
    // parede, onde quase sempre ha um ponto medido por perto.
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = 3;
    ctx.strokeStyle = css('--surface-1');
    ctx.strokeText('roteador', rx, ry + 24);
    ctx.fillStyle = css('--ink-2');
    ctx.fillText('roteador', rx, ry + 24);

    const hits = [];
    spec.points.forEach((p) => {
      const X = px(p.x);
      const Y = py(p.y);
      const r = 6.5 + Math.min(7, Math.sqrt(p.n) * 1.2);  // marcas >= 8px de diametro
      ctx.beginPath(); ctx.arc(X, Y, r + 2, 0, Math.PI * 2);
      ctx.fillStyle = css('--surface-1'); ctx.fill();
      ctx.beginPath(); ctx.arc(X, Y, r, 0, Math.PI * 2);
      ctx.fillStyle = p.color; ctx.fill();
      ctx.fillStyle = css('--ink-1');
      ctx.font = '10px system-ui, -apple-system, sans-serif';
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(Math.round(p.value) + '%', X, Y);
      hits.push({ x: X, y: Y, r: r + 6, label: p.label, value: p.value, at: `${p.n} amostras`, color: p.color });
    });
    return hits;
  };

  /* ---------- hover partilhado ---------- */
  VENKO.attachTooltip = function (canvas, tip, getHits, fmt) {
    function move(ev) {
      const rect = canvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      let best = null;
      let bestD = Infinity;
      (getHits() || []).forEach((h) => {
        const d = Math.hypot(h.x - mx, h.y - my);
        if (d < h.r && d < bestD) { best = h; bestD = d; }
      });
      if (!best) { tip.style.opacity = 0; return; }
      tip.innerHTML = fmt(best);
      tip.style.opacity = 1;
      const tw = tip.offsetWidth;
      tip.style.left = Math.max(0, Math.min(canvas.clientWidth - tw, best.x - tw / 2)) + 'px';
      tip.style.top = (best.y - tip.offsetHeight - 12) + 'px';
    }
    canvas.addEventListener('mousemove', move);
    canvas.addEventListener('mouseleave', () => { tip.style.opacity = 0; });
  };
})();
