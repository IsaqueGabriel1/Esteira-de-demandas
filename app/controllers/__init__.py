"""Controllers (camada C do MVC): recebem a requisição, chamam os serviços e devolvem a view."""
from flask import flash, jsonify, redirect, render_template, request, url_for

from ..services.erros import PermissaoNegada


def registrar_blueprints(app):
    from .auth import bp as auth_bp
    from .demandas import bp as demandas_bp
    from .divisoes import bp as divisoes_bp
    from .indicadores import bp as indicadores_bp
    from .usuarios import bp as usuarios_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(demandas_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(divisoes_bp)
    app.register_blueprint(indicadores_bp)

    def _quer_json():
        return request.is_json or request.accept_mimetypes.best == "application/json"

    @app.errorhandler(PermissaoNegada)
    def permissao_negada(erro):
        if _quer_json():
            return jsonify(ok=False, erro=erro.mensagem), 403
        return render_template("errors/403.html", mensagem=erro.mensagem), 403

    @app.errorhandler(403)
    def proibido(_erro):
        if _quer_json():
            return jsonify(ok=False, erro="Acesso negado."), 403
        return render_template("errors/403.html", mensagem="Você não tem permissão para acessar esta página."), 403

    @app.errorhandler(404)
    def nao_encontrado(_erro):
        if _quer_json():
            return jsonify(ok=False, erro="Não encontrado."), 404
        return render_template("errors/404.html"), 404

    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def csrf_invalido(_erro):
        if _quer_json():
            return jsonify(ok=False, erro="Sessão expirada. Recarregue a página."), 400
        flash("Sua sessão expirou. Tente novamente.", "warning")
        return redirect(request.referrer or url_for("demandas.quadro"))
