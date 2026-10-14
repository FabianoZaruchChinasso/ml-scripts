/* laboratorio.js — área Laboratório: análises de apoio que mudam pouco no dia a dia.
   Um seletor de alvo (#labAlvo) vale para as três partes: Features, Desenho e Paralelos. */
(function () {
  'use strict';
  const V = window.VENKO;
  const $ = (s) => document.querySelector(s);
  let ultimo = null;

  function render(ctx) {
    ultimo = ctx;
    V.views.features.render(ctx);
    V.views.desenho.render(ctx);
    V.views.paralelos.render(ctx);
  }

  // features.js e paralelos.js escutam #labAlvo por conta própria; o desenho só redesenha.
  $('#labAlvo').addEventListener('change', () => { if (ultimo) V.views.desenho.render(ultimo); });

  V.areas = V.areas || {};
  V.areas.laboratorio = { render };
})();
