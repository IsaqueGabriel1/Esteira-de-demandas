/* Gráficos do painel de indicadores (Chart.js) */
(function () {
  'use strict';

  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
    new bootstrap.Tooltip(el);
  });

  var dados = JSON.parse(document.getElementById('dados-graficos').textContent);
  var PRIMARIA = '#0b4f71';
  var CORES_STATUS = ['#adb5bd', '#ffc107', '#0dcaf0', '#0d6efd', '#6f42c1', '#198754', '#dc3545', '#6c757d'];

  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.plugins.legend.display = false;

  function barras(id, serie, opcoes) {
    opcoes = opcoes || {};
    return new Chart(document.getElementById(id), {
      type: 'bar',
      data: {
        labels: serie.rotulos,
        datasets: [{ data: serie.valores, backgroundColor: opcoes.cores || PRIMARIA, borderRadius: 4 }]
      },
      options: {
        aspectRatio: 2.2,
        indexAxis: opcoes.horizontal ? 'y' : 'x',
        scales: { x: { ticks: { precision: 0 } }, y: { ticks: { precision: 0 }, beginAtZero: true } },
        plugins: { tooltip: { callbacks: opcoes.tooltip || {} } }
      }
    });
  }

  if (document.getElementById('g-etapas')) {
    barras('g-etapas', dados.etapas, {
      horizontal: true,
      cores: ['#ffc107', '#0dcaf0', '#0d6efd', '#6f42c1'],
      tooltip: { label: function (item) { return 'Mediana: ' + dados.etapas.textos[item.dataIndex]; } }
    });
  }

  barras('g-eixo', dados.eixo, {
    tooltip: { title: function (itens) { return dados.eixo.rotulos[itens[0].dataIndex] + ' — ' + dados.eixo.nomes[itens[0].dataIndex]; } }
  });
  barras('g-status', dados.status, { cores: CORES_STATUS });
  if (document.getElementById('g-carga')) {
    barras('g-carga', dados.carga, {
      horizontal: true,
      tooltip: { label: function (item) { return item.raw + ' pontos GUT em ' + dados.carga.ativas[item.dataIndex] + ' demanda(s) ativa(s)'; } }
    });
  }
})();
