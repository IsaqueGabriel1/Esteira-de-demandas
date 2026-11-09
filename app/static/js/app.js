/* Configuração comum a todas as páginas */
(function ($) {
  'use strict';

  // Envia o token CSRF em todas as requisições AJAX (Flask-WTF lê o cabeçalho X-CSRFToken)
  var token = $('meta[name="csrf-token"]').attr('content');
  $.ajaxSetup({
    headers: { 'X-CSRFToken': token },
    contentType: 'application/json; charset=utf-8',
    dataType: 'json'
  });

  // Mensagem rápida no canto da tela
  window.mostrarAviso = function (mensagem, tipo) {
    var cor = tipo === 'erro' ? 'text-bg-danger' : 'text-bg-success';
    var $toast = $(
      '<div class="toast align-items-center border-0 ' + cor + '" role="alert">' +
        '<div class="d-flex"><div class="toast-body"></div>' +
        '<button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>' +
      '</div>'
    );
    $toast.find('.toast-body').text(mensagem);
    $('#toasts').append($toast);
    var t = new bootstrap.Toast($toast[0], { delay: 5000 });
    $toast.on('hidden.bs.toast', function () { $toast.remove(); });
    t.show();
  };

  // Botões "Copiar" (data-copiar="texto"). Em HTTP sem TLS a API de área de
  // transferência não existe, então usa o método antigo como alternativa.
  $(document).on('click', '[data-copiar]', function () {
    var texto = $(this).attr('data-copiar');
    var ok = function () { mostrarAviso('Copiado para a área de transferência.'); };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(texto).then(ok, function () { mostrarAviso('Não foi possível copiar.', 'erro'); });
      return;
    }
    var $campo = $('<textarea readonly>').val(texto).css({ position: 'fixed', opacity: 0 }).appendTo('body');
    $campo[0].select();
    try { document.execCommand('copy'); ok(); } catch (e) { mostrarAviso('Não foi possível copiar.', 'erro'); }
    $campo.remove();
  });
})(jQuery);
