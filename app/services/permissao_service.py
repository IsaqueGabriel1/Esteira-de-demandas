"""Permissões por perfil configuráveis pelo Administrador (tela Permissões)."""
from ..extensions import db
from ..models import HistoricoPermissao, PermissaoPerfil
from . import permissoes
from .erros import PermissaoNegada, RegraNegocioError
from .perfis import Perfil


def carregar():
    """Aplica em permissoes.py as alterações gravadas no banco.

    Chamado a cada requisição (são poucas linhas) para que todos os workers do
    Gunicorn vejam a mesma configuração logo após uma alteração.
    """
    permissoes.configurar({(p.perfil, p.chave): p.ativo for p in PermissaoPerfil.query.all()})


def matriz():
    """{(perfil, chave): ativo} com a configuração em vigor para todos os perfis."""
    return {(perfil, chave): permissoes.permitido(perfil, chave) for perfil in Perfil.TODOS for chave in permissoes.CHAVES}


def _exigir_administrador(usuario):
    from .usuario_service import eh_administrador

    if not eh_administrador(usuario):
        raise PermissaoNegada("Apenas o Administrador pode alterar as permissões.")


def salvar(admin, ativas):
    """ativas: conjunto de (perfil, chave) marcados na tela. Retorna quantas mudaram."""
    _exigir_administrador(admin)
    invalidas = {(p, c) for p, c in ativas if p not in Perfil.TODOS or c not in permissoes.CHAVES}
    if invalidas:
        raise RegraNegocioError("Permissão desconhecida.")

    atuais = matriz()
    gravadas = {(p.perfil, p.chave): p for p in PermissaoPerfil.query.all()}
    alteradas = 0
    for (perfil, chave), antes in atuais.items():
        depois = (perfil, chave) in ativas
        if depois != antes:
            db.session.add(HistoricoPermissao(perfil=perfil, chave=chave, antes=antes, depois=depois, usuario_id=admin.id))
            alteradas += 1
        linha = gravadas.get((perfil, chave))
        if depois == permissoes.padrao(perfil, chave):
            if linha:
                db.session.delete(linha)
        elif linha:
            linha.ativo = depois
        else:
            db.session.add(PermissaoPerfil(perfil=perfil, chave=chave, ativo=depois))
    db.session.commit()
    carregar()
    return alteradas


def restaurar_padrao(admin):
    ativas = {(p, c) for p in Perfil.TODOS for c in permissoes.CHAVES if permissoes.padrao(p, c)}
    return salvar(admin, ativas)


def historico(limite=30):
    return HistoricoPermissao.query.order_by(HistoricoPermissao.id.desc()).limit(limite).all()
