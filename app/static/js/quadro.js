/* Quadro kanban: arrastar e soltar com validação no servidor */
(function ($) {
  'use strict';

  // Movimentos aceitos por arraste (espelha app/services/fluxo.py -> ACOES_POR_ARRASTE).
  // O servidor sempre valida novamente; isto serve apenas para destacar as colunas possíveis.
  var MOVIMENTOS = {
    'AGUARDANDO_ACEITE': ['EM_ANDAMENTO'],
    'EM_ANDAMENTO': ['EM_REVISAO'],
    'EM_REVISAO': ['CONCLUIDA']
  };

  function atualizarContadores() {
    $('.coluna').each(function () {
      var $coluna = $(this);
      var qtd = $coluna.find('.card-demanda').length;
      $coluna.find('.contador').text(qtd);
      $coluna.find('.coluna-vazia').toggle(qtd === 0);
    });
  }

  function urlMover(id) {
    return window.URL_MOVER.replace(/\/0\/mover$/, '/' + id + '/mover');
  }

  $('.coluna-cards').each(function () {
    if (!$(this).find('.coluna-vazia').length) {
      $(this).append('<div class="coluna-vazia" style="display:none">Nenhuma demanda</div>');
    }
    new Sortable(this, {
      group: 'quadro',
      sort: false,
      animation: 150,
      draggable: '.card-demanda',
      onStart: function (evt) {
        var destinos = MOVIMENTOS[evt.from.dataset.status] || [];
        destinos.forEach(function (s) { $('.coluna-cards[data-status="' + s + '"]').addClass('destino-valido'); });
      },
      onEnd: function (evt) {
        $('.coluna-cards').removeClass('destino-valido');
        if (evt.from === evt.to) { return; }

        var $card = $(evt.item);
        var origem = evt.from;
        var indiceOriginal = evt.oldIndex;
        var destino = evt.to.dataset.status;

        function desfazer() {
          var filhos = origem.querySelectorAll('.card-demanda');
          if (indiceOriginal >= filhos.length) { origem.appendChild(evt.item); }
          else { origem.insertBefore(evt.item, filhos[indiceOriginal]); }
          atualizarContadores();
        }

        atualizarContadores();
        $.ajax({
          url: urlMover($card.data('id')),
          method: 'POST',
          data: JSON.stringify({ status: destino })
        }).done(function (resp) {
          $card.attr('data-status', resp.status);
          mostrarAviso('Demanda #' + $card.data('id') + ': ' + resp.rotulo + '.');
        }).fail(function (xhr) {
          var erro = (xhr.responseJSON && xhr.responseJSON.erro) || 'Não foi possível mover a demanda.';
          mostrarAviso(erro, 'erro');
          desfazer();
        });
      }
    });
  });
})(jQuery);
