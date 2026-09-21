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

  /* ---------- planta baixa: pontos medidos, sem interpolacao ----------
     Tudo chega em cm. `papel` leva o referencial dos dados para a orientacao do
     desenho original; em paisagem/retrato um giro de 90 graus deixa o lado maior
     na horizontal/vertical. Uma unica transformacao serve pontos, paredes e foto. */
  function matrizTela(papel, W, H, orient) {
    const P = papel || [[1, 0], [0, 1]];
    const w = Math.abs(P[0][0] * W + P[0][1] * H);
    const h = Math.abs(P[1][0] * W + P[1][1] * H);
    const girar = orient === 'paisagem' ? h > w : w > h;
    // Giro horario com y para baixo: (x, y) -> (-y, x).
    return girar ? [[-P[1][0], -P[1][1]], [P[0][0], P[0][1]]] : P;
  }

  VENKO.drawFloorPlan = function (canvas, spec) {
    const env = spec.envelope;
    const W = env.w;
    const H = env.h;
    const M = matrizTela(spec.papel, W, H, spec.orient);
    const m = spec.margem || 0;
    const girado = (x, y) => [M[0][0] * x + M[0][1] * y, M[1][0] * x + M[1][1] * y];
    const caixa = [[-m, -m], [W + m, -m], [W + m, H + m], [-m, H + m]].map(([x, y]) => girado(x, y));
    const minX = Math.min(...caixa.map((c) => c[0]));
    const maxX = Math.max(...caixa.map((c) => c[0]));
    const minY = Math.min(...caixa.map((c) => c[1]));
    const maxY = Math.max(...caixa.map((c) => c[1]));
    // Folga suficiente para o raio da maior marca nao vazar o desenho.
    const pad = 34;
    const width = canvas.clientWidth;
    const altura = spec.orient === 'paisagem'
      ? Math.max(220, Math.min(520, Math.round((width - pad * 2) * (maxY - minY) / (maxX - minX) + pad * 2)))
      : (spec.altura || 640);
    const { ctx } = prepare(canvas, altura);
    const s = Math.min((width - pad * 2) / (maxX - minX), (altura - pad * 2) / (maxY - minY));
    const tx = (width - (maxX - minX) * s) / 2 - minX * s;
    const ty = (altura - (maxY - minY) * s) / 2 - minY * s;
    const T = (x, y) => { const g = girado(x, y); return [tx + s * g[0], ty + s * g[1]]; };

    if (spec.foto) {
      const ratio = window.devicePixelRatio || 1;
      ctx.save();
      ctx.setTransform(ratio * s * M[0][0], ratio * s * M[1][0], ratio * s * M[0][1], ratio * s * M[1][1],
                       ratio * tx, ratio * ty);
      ctx.globalAlpha = spec.fotoAlpha;
      if (spec.escuro) {
        if ('filter' in ctx) ctx.filter = 'invert(1) hue-rotate(180deg)';
        else ctx.globalAlpha = Math.min(spec.fotoAlpha, 0.15);
      }
      // A foto endireitada tem 1 px = 1 cm e comeca em (-margem, -margem).
      ctx.drawImage(spec.foto.img, -spec.foto.margem, -spec.foto.margem,
                    W + 2 * spec.foto.margem, H + 2 * spec.foto.margem);
      ctx.restore();
    }

    const quinas = [[0, 0], [W, 0], [W, H], [0, H]].map(([x, y]) => T(x, y));
    if (!spec.paredes && !spec.foto) {
      ctx.strokeStyle = css('--axis');
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      quinas.forEach(([X, Y], i) => (i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y)));
      ctx.closePath();
      ctx.stroke();
    }
    if (spec.paredes) {
      ctx.strokeStyle = css('--ink-1');
      ctx.lineWidth = 2;
      ctx.lineCap = 'square';
      ctx.beginPath();
      spec.paredes.forEach(([x1, y1, x2, y2]) => {
        const a = T(x1, y1);
        const b = T(x2, y2);
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
      });
      ctx.stroke();
    }

    // Rotulos fora da caixa com margem: por dentro, cairiam sobre a foto.
    const esq = tx + s * minX;
    const dir = tx + s * maxX;
    const cima = ty + s * minY;
    const baixo = ty + s * maxY;
    const horizontal = M[0][0] !== 0 ? W : H;
    ctx.fillStyle = css('--ink-muted');
    ctx.font = '10.5px system-ui, -apple-system, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(`${horizontal} cm`, (esq + dir) / 2, cima - 12);
    ctx.save();
    ctx.translate(esq - 13, (cima + baixo) / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(`${horizontal === W ? H : W} cm`, 0, 0);
    ctx.restore();

    // Roteador: marca de identidade, nunca uma cor de serie.
    const [rx, ry] = T(env.routerX, env.routerY);
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
    ctx.lineWidth = 3;
    ctx.strokeStyle = css('--surface-1');
    ctx.strokeText('roteador', rx, ry + 24);
    ctx.fillStyle = css('--ink-2');
    ctx.fillText('roteador', rx, ry + 24);

    const hits = [];
    spec.points.forEach((p) => {
      const [X, Y] = T(p.x, p.y);
      const r = 6.5 + Math.min(7, Math.sqrt(p.n) * 1.2);  // marcas >= 8px de diametro
      ctx.beginPath(); ctx.arc(X, Y, r + 2, 0, Math.PI * 2);
      ctx.fillStyle = css('--surface-1'); ctx.fill();
      ctx.beginPath(); ctx.arc(X, Y, r, 0, Math.PI * 2);
      ctx.fillStyle = p.color; ctx.fill();
      // A rampa sequencial e a mesma nos dois temas: a cor do texto segue o fundo, nao o tema.
      ctx.fillStyle = p.value > 55 ? '#ffffff' : '#0b0b0b';
      ctx.font = '10px system-ui, -apple-system, sans-serif';
      ctx.fillText(Math.round(p.value) + '%', X, Y);
      hits.push({ x: X, y: Y, r: r + 6, label: p.label, value: p.value, at: `${p.n} amostras`, color: p.color });
    });
    return hits;
  };

  /* ---------- pontos por linha: teto de desempenho ----------
     Eixo truncado de proposito: barras a partir de zero esconderiam
     diferencas de 0,02 entre conjuntos. Ponto nao carrega essa mentira. */
  VENKO.drawDotRows = function (canvas, spec) {
    const rowH = 52;
    const top = 10;
    const bottom = 30;
    const H = top + spec.rows.length * rowH + bottom;
    const { ctx, width } = prepare(canvas, H);
    const left = 178;
    const right = 74;
    const all = spec.rows.flatMap((r) => r.points.map((p) => p.v).concat([r.mean]))
      .filter((v) => v != null);
    if (!all.length) return [];
    let lo = Math.min(...all);
    let hi = Math.max(...all);
    const pad = Math.max(0.02, (hi - lo) * 0.08);
    lo -= pad; hi += pad;
    const x = (v) => left + ((v - lo) / (hi - lo)) * (width - left - right);
    const fmt = spec.fmt || ((v) => v.toFixed(2));
    const font = '11px system-ui, -apple-system, sans-serif';
    const bold = '600 12.5px system-ui, -apple-system, sans-serif';

    ctx.strokeStyle = css('--grid');
    ctx.lineWidth = 1;
    ctx.fillStyle = css('--ink-muted');
    ctx.font = font;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    niceTicks(lo, hi, 5).filter((t) => t >= lo && t <= hi).forEach((t) => {
      const X = Math.round(x(t)) + 0.5;
      ctx.beginPath(); ctx.moveTo(X, top); ctx.lineTo(X, H - bottom); ctx.stroke();
      ctx.fillText(fmt(t), X, H - bottom + 8);
    });

    const hits = [];
    spec.rows.forEach((r, i) => {
      const cy = top + i * rowH + rowH / 2;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = css('--ink-1'); ctx.font = bold;
      ctx.fillText(r.label, 0, cy - 7);
      ctx.fillStyle = css('--ink-muted'); ctx.font = font;
      ctx.fillText(r.sub, 0, cy + 9);
      if (r.mean != null) {
        ctx.strokeStyle = css('--ink-1'); ctx.lineWidth = 2.5;
        ctx.beginPath(); ctx.moveTo(x(r.mean), cy - 15); ctx.lineTo(x(r.mean), cy + 15); ctx.stroke();
        ctx.fillStyle = css('--ink-1'); ctx.font = bold;
        ctx.fillText((spec.fmtMean || fmt)(r.mean), width - right + 14, cy);
        hits.push({ x: x(r.mean), y: cy, r: 10, label: r.label, value: r.mean, at: 'média' });
      }
      r.points.forEach((p) => {
        const X = x(p.v);
        // Anel na cor da superficie: pontos de posicoes vizinhas nao se fundem.
        ctx.beginPath(); ctx.arc(X, cy, 7, 0, Math.PI * 2); ctx.fillStyle = css('--surface-1'); ctx.fill();
        ctx.beginPath(); ctx.arc(X, cy, 5.5, 0, Math.PI * 2); ctx.fillStyle = p.color; ctx.fill();
        hits.push({ x: X, y: cy, r: 9, label: r.label, value: p.v, at: p.key, color: p.color });
      });
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
