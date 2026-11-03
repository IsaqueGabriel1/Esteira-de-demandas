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
})(jQuery);
