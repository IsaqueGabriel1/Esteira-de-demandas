/* Formulário de demanda: Select2 nos campos de usuários e cálculo visual de P */
(function ($) {
  'use strict';

  var $atribuido = $('#atribuido_id');
  var $apoio = $('#apoio_ids');

  $atribuido.select2({ theme: 'bootstrap-5', language: 'pt-BR', width: '100%' });
  $apoio.select2({
    theme: 'bootstrap-5', language: 'pt-BR', width: '100%',
    placeholder: 'Selecione os usuários de apoio', closeOnSelect: false
  });

  // O atribuído não pode ser apoio: desabilita a opção correspondente no campo de apoio
  function sincronizarApoio() {
    var atribuido = $atribuido.val();
    $apoio.find('option').prop('disabled', false);
    if (atribuido && atribuido !== '0') {
      var $opcao = $apoio.find('option[value="' + atribuido + '"]');
      $opcao.prop('selected', false).prop('disabled', true);
    }
    $apoio.trigger('change.select2');
  }
  $atribuido.on('change', sincronizarApoio);
  sincronizarApoio();

  // P = G × U × T (apenas exibição; o valor oficial é calculado no servidor)
  function recalcular() {
    var v = $('.peso-gut').map(function () { return parseInt($(this).val(), 10) || 0; }).get();
    var ok = v.length === 3 && v.every(function (n) { return n >= 1 && n <= 5; });
    $('#p-calculado').text(ok ? v[0] * v[1] * v[2] : '—');
  }
  $('.peso-gut').on('change', recalcular);
  recalcular();
})(jQuery);
