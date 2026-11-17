/* Gráfico da tela de uso do sistema (Chart.js) */
(function () {
  'use strict';

  var dados = JSON.parse(document.getElementById('dados-graficos').textContent);
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

  new Chart(document.getElementById('g-dias'), {
    type: 'line',
    data: {
      labels: dados.dias.rotulos,
      datasets: [
        { label: 'Pessoas que usaram', data: dados.dias.pessoas, borderColor: '#0b4f71', backgroundColor: '#0b4f71', tension: 0.3 },
        { label: 'Logins com sucesso', data: dados.dias.logins, borderColor: '#198754', backgroundColor: '#198754', tension: 0.3 },
        { label: 'Tentativas com erro', data: dados.dias.falhas, borderColor: '#dc3545', backgroundColor: '#dc3545', tension: 0.3 }
      ]
    },
    options: {
      interaction: { mode: 'index', intersect: false },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
      plugins: { legend: { position: 'bottom' } }
    }
  });
})();
