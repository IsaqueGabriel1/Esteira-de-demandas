"""Divisões: cadastradas pelo Administrador e usadas no cadastro de usuários e nas demandas."""
from ..extensions import db
from ..models import Divisao
from .erros import PermissaoNegada, RegraNegocioError

TAMANHO_MAXIMO_SIGLA = 20

# Carga inicial: (sigla, aparece para usuários, aparece nas demandas). A ordem define a ordem das opções.
DIVISOES_PADRAO = [
    ("DIO", True, True),
    ("DPO", True, True),
    ("GGO", True, True),
    ("SR", True, False),
    ("DIO/DPO", False, True),
    ("DPO/DIO", False, True),
    ("GGO/DPO/DIO", False, True),
]


def carregar_padrao():
    """Cadastra as divisões padrão que ainda não existirem. Retorna quantas foram criadas."""
    existentes = {d.sigla for d in Divisao.query.all()}
    criadas = 0
    for sigla, para_usuarios, para_demandas in DIVISOES_PADRAO:
        if sigla not in existentes:
            db.session.add(Divisao(sigla=sigla, para_usuarios=para_usuarios, para_demandas=para_demandas))
            criadas += 1
    db.session.commit()
    return criadas


# ---------------------------------------------------------------------------
# Consultas (opções dos formulários)
# ---------------------------------------------------------------------------

def listar_todas():
    return Divisao.query.order_by(Divisao.ativa.desc(), Divisao.id).all()


def _siglas(filtro, atual=None):
    """Siglas ativas do tipo pedido. 'atual' entra na lista mesmo se desativada,
    para que editar um registro antigo não obrigue a trocar a divisão."""
    siglas = [d.sigla for d in Divisao.query.filter_by(ativa=True).filter(filtro).order_by(Divisao.id)]
    if atual and atual not in siglas:
        siglas.append(atual)
    return siglas


def siglas_para_usuarios(atual=None):
    return _siglas(Divisao.para_usuarios.is_(True), atual)


def siglas_para_demandas(atual=None):
    return _siglas(Divisao.para_demandas.is_(True), atual)


def validar_para_usuario(valor, obrigatoria=True, atual=None):
    if not valor and not obrigatoria:
        return None
    opcoes = siglas_para_usuarios(atual)
    if valor not in opcoes:
        raise RegraNegocioError("Selecione a divisão: " + ", ".join(opcoes) + ".")
    return valor


def validar_para_demanda(valor, atual=None):
    opcoes = siglas_para_demandas(atual)
    if valor not in opcoes:
        raise RegraNegocioError("Selecione a divisão: " + ", ".join(opcoes) + ".")
    return valor


# ---------------------------------------------------------------------------
# Gestão (somente o Administrador)
# ---------------------------------------------------------------------------

def _exigir_administrador(usuario):
    from .usuario_service import eh_administrador

    if not eh_administrador(usuario):
        raise PermissaoNegada("Apenas o Administrador pode gerenciar as divisões.")


def _validar_uso(para_usuarios, para_demandas):
    if not para_usuarios and not para_demandas:
        raise RegraNegocioError("Marque onde a divisão aparece: no cadastro de usuários, nas demandas ou em ambos.")


def criar(admin, sigla, para_usuarios=True, para_demandas=True):
    _exigir_administrador(admin)
    sigla = " ".join((sigla or "").split()).upper()
    if not sigla:
        raise RegraNegocioError("Informe a sigla da divisão.")
    if len(sigla) > TAMANHO_MAXIMO_SIGLA:
        raise RegraNegocioError(f"A sigla deve ter no máximo {TAMANHO_MAXIMO_SIGLA} caracteres.")
    if Divisao.query.filter_by(sigla=sigla).first():
        raise RegraNegocioError(f"A divisão {sigla} já está cadastrada.")
    _validar_uso(para_usuarios, para_demandas)

    divisao = Divisao(sigla=sigla, para_usuarios=bool(para_usuarios), para_demandas=bool(para_demandas), ativa=True)
    db.session.add(divisao)
    db.session.commit()
    return divisao


def atualizar(admin, divisao, para_usuarios, para_demandas, ativa):
    """A sigla não muda: usuários e demandas guardam a sigla como texto."""
    _exigir_administrador(admin)
    _validar_uso(para_usuarios, para_demandas)
    divisao.para_usuarios = bool(para_usuarios)
    divisao.para_demandas = bool(para_demandas)
    divisao.ativa = bool(ativa)
    db.session.commit()
    return divisao


def contar_uso():
    """{sigla: (nº de usuários, nº de demandas)} — exibido na lista de divisões."""
    from sqlalchemy import func

    from ..models import Demanda, Usuario

    usuarios = dict(db.session.query(Usuario.divisao, func.count()).group_by(Usuario.divisao).all())
    demandas = dict(db.session.query(Demanda.divisao, func.count()).group_by(Demanda.divisao).all())
    return {sigla: (usuarios.get(sigla, 0), demandas.get(sigla, 0)) for sigla in set(usuarios) | set(demandas) if sigla}
