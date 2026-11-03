from functools import wraps

from flask import abort
from flask_login import current_user, login_required


def perfil_requerido(*perfis):
    """Restringe a rota aos perfis informados (além de exigir login)."""
    def decorador(funcao):
        @wraps(funcao)
        @login_required
        def envoltorio(*args, **kwargs):
            if current_user.perfil not in perfis:
                abort(403)
            return funcao(*args, **kwargs)
        return envoltorio
    return decorador
