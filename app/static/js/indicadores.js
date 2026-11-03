/* Gráficos do painel de indicadores (Chart.js) */
(function () {
  'use strict';

  var dados = JSON.parse(document.getElementById('dados-graficos').textContent);
  var PRIMARIA = '#0b4f71';
  var CORES_STATUS = ['#adb5bd', '#ffc107', '#0d6efd', '#6f42c1', '#198754', '#dc3545', '#6c757d'];
  var CORES_FAIXA = ['#c62828', '#ef8f00', '#2e7d32', '#8a94a6'];

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

  barras('g-eixo', dados.eixo, {
    tooltip: { title: function (itens) { return dados.eixo.rotulos[itens[0].dataIndex] + ' — ' + dados.eixo.nomes[itens[0].dataIndex]; } }
  });
  barras('g-status', dados.status, { cores: CORES_STATUS });
  barras('g-responsavel', dados.responsavel, { horizontal: true });
  barras('g-faixa', dados.faixa, { cores: CORES_FAIXA });
})();
