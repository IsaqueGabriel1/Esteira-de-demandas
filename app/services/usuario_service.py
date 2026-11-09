"""Regras de negócio de usuários: autenticação, autocadastro e gestão (restrita ao Gerente)."""
from flask import current_app

from ..extensions import db
from ..models import Usuario
from . import permissoes
from .divisoes import DivisaoUsuario
from .erros import PermissaoNegada, RegraNegocioError
from .perfis import Perfil

TAMANHO_MINIMO_SENHA = 8


def _normalizar_email(email):
    return (email or "").strip().lower()


def autenticar(email, senha):
    """Retorna o usuário se e-mail e senha conferem e ele está ativo; senão None."""
    usuario = Usuario.query.filter_by(email=_normalizar_email(email)).first()
    if usuario and usuario.ativo and usuario.verificar_senha(senha or ""):
        return usuario
    return None


def eh_administrador(usuario):
    """O Administrador é a conta criada pelo 'flask seed' (ADMIN_EMAIL do .env)."""
    return usuario.email == _normalizar_email(current_app.config.get("ADMIN_EMAIL"))


def precisa_informar_divisao(usuario):
    return not usuario.divisao and not eh_administrador(usuario)


def _validar_divisao(divisao, obrigatoria=True):
    if not divisao and not obrigatoria:
        return None
    if divisao not in DivisaoUsuario.TODAS:
        raise RegraNegocioError("Selecione a divisão: " + ", ".join(DivisaoUsuario.TODAS) + ".")
    return divisao


def definir_propria_divisao(usuario, divisao):
    usuario.divisao = _validar_divisao(divisao)
    db.session.commit()


def aguardando_aprovacao(email, senha):
    """True se e-mail e senha conferem, mas a conta ainda está inativa."""
    usuario = Usuario.query.filter_by(email=_normalizar_email(email)).first()
    return bool(usuario and not usuario.ativo and usuario.verificar_senha(senha or ""))


def autocadastrar(nome, email, senha, divisao):
    """Cadastro feito pela própria pessoa: sempre Usuário Comum e inativo,
    até que um Gerente ative a conta em Usuários."""
    nome, email = _validar_dados(nome, email, Perfil.USUARIO)
    divisao = _validar_divisao(divisao)
    _validar_senha(senha)
    usuario = Usuario(nome=nome, email=email, perfil=Perfil.USUARIO, divisao=divisao, ativo=False)
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()
    return usuario


def listar_ativos():
    return Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()


def listar_todos():
    return Usuario.query.order_by(Usuario.ativo.desc(), Usuario.nome).all()


def _exigir_admin(usuario):
    if not permissoes.pode_gerenciar_usuarios(usuario.perfil):
        raise PermissaoNegada("Apenas o Gerente pode gerenciar usuários.")


def _validar_senha(senha):
    if not senha or len(senha) < TAMANHO_MINIMO_SENHA:
        raise RegraNegocioError(f"A senha deve ter pelo menos {TAMANHO_MINIMO_SENHA} caracteres.")


def _validar_dados(nome, email, perfil, ignorar_id=None):
    nome = (nome or "").strip()
    email = _normalizar_email(email)
    if not nome:
        raise RegraNegocioError("Informe o nome.")
    if not email or "@" not in email:
        raise RegraNegocioError("Informe um e-mail válido.")
    if perfil not in Perfil.TODOS:
        raise RegraNegocioError("Perfil inválido.")
    existente = Usuario.query.filter_by(email=email).first()
    if existente and existente.id != ignorar_id:
        raise RegraNegocioError("Já existe um usuário com este e-mail.")
    return nome, email


def _gerentes_ativos(excluir_id=None):
    consulta = Usuario.query.filter_by(perfil=Perfil.GERENTE, ativo=True)
    if excluir_id:
        consulta = consulta.filter(Usuario.id != excluir_id)
    return consulta.count()


def criar(admin, nome, email, perfil, senha, divisao=None):
    """Sem divisão, o próprio usuário a informa no primeiro acesso."""
    _exigir_admin(admin)
    nome, email = _validar_dados(nome, email, perfil)
    divisao = _validar_divisao(divisao, obrigatoria=False)
    _validar_senha(senha)
    usuario = Usuario(nome=nome, email=email, perfil=perfil, divisao=divisao, ativo=True)
    usuario.definir_senha(senha)
    db.session.add(usuario)
    db.session.commit()
    return usuario


def atualizar(admin, usuario, nome, email, perfil, ativo=True, nova_senha=None, divisao=None):
    _exigir_admin(admin)
    nome, email = _validar_dados(nome, email, perfil, ignorar_id=usuario.id)
    divisao = _validar_divisao(divisao, obrigatoria=False)
    deixa_de_ser_gerente_ativo = usuario.perfil == Perfil.GERENTE and (perfil != Perfil.GERENTE or not ativo)
    if deixa_de_ser_gerente_ativo and _gerentes_ativos(excluir_id=usuario.id) == 0:
        raise RegraNegocioError("O sistema precisa ter pelo menos um Gerente ativo.")
    if usuario.id == admin.id and not ativo:
        raise RegraNegocioError("Você não pode desativar o seu próprio usuário.")

    usuario.nome, usuario.email, usuario.perfil, usuario.ativo = nome, email, perfil, bool(ativo)
    usuario.divisao = divisao
    if nova_senha:
        _validar_senha(nova_senha)
        usuario.definir_senha(nova_senha)
    db.session.commit()
    return usuario


def alterar_propria_senha(usuario, senha_atual, nova_senha):
    if not usuario.verificar_senha(senha_atual or ""):
        raise RegraNegocioError("A senha atual não confere.")
    _validar_senha(nova_senha)
    usuario.definir_senha(nova_senha)
    db.session.commit()
