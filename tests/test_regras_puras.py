"""Regras puras: GUT, permissões e máquina de estados (não usam banco)."""
import pytest

from app.services import gut, permissoes
from app.services.erros import RegraNegocioError, TransicaoInvalida
from app.services.fluxo import Acao, Status, acao_por_arraste, proximo_status
from app.services.perfis import Perfil


# ---------------- GUT ----------------

def test_prioridade_e_o_produto_dos_pesos():
    assert gut.calcular_prioridade(5, 4, 3) == 60
    assert gut.calcular_prioridade(1, 1, 1) == 1
    assert gut.calcular_prioridade(5, 5, 5) == 125


def test_prioridade_sem_todos_os_pesos_e_none():
    assert gut.calcular_prioridade(5, None, 3) is None


@pytest.mark.parametrize("valor", [0, 6, -1, "x", 2.5j])
def test_peso_fora_do_intervalo_e_rejeitado(valor):
    with pytest.raises(RegraNegocioError):
        gut.calcular_prioridade(valor, 3, 3)


@pytest.mark.parametrize("p, esperado", [
    (1, "baixa"), (27, "baixa"), (28, "media"), (63, "media"), (64, "alta"), (125, "alta"), (None, "pendente"),
])
def test_faixas(p, esperado):
    assert gut.faixa(p)[1] == esperado


def test_faixas_cobrem_todos_os_valores_possiveis():
    possiveis = {g * u * t for g in range(1, 6) for u in range(1, 6) for t in range(1, 6)}
    for p in possiveis:
        gut.faixa(p)  # não lança erro


# ---------------- Permissões ----------------

@pytest.mark.parametrize("destino", Perfil.TODOS)
def test_gerente_atribui_a_qualquer_perfil(destino):
    assert permissoes.pode_atribuir(Perfil.GERENTE, destino)


def test_chefe_atribui_somente_a_usuario_comum():
    assert permissoes.pode_atribuir(Perfil.CHEFE, Perfil.USUARIO)
    assert not permissoes.pode_atribuir(Perfil.CHEFE, Perfil.CHEFE)
    assert not permissoes.pode_atribuir(Perfil.CHEFE, Perfil.GERENTE)


@pytest.mark.parametrize("destino", Perfil.TODOS)
def test_usuario_comum_nao_atribui(destino):
    assert not permissoes.pode_atribuir(Perfil.USUARIO, destino)


def test_gut_somente_gestores():
    assert permissoes.pode_definir_gut(Perfil.GERENTE)
    assert permissoes.pode_definir_gut(Perfil.CHEFE)
    assert not permissoes.pode_definir_gut(Perfil.USUARIO)


def test_revisao():
    assert permissoes.pode_revisar(Perfil.GERENTE, eh_o_atribuido=True)
    assert permissoes.pode_revisar(Perfil.CHEFE, eh_o_atribuido=False)
    assert not permissoes.pode_revisar(Perfil.CHEFE, eh_o_atribuido=True)
    assert not permissoes.pode_revisar(Perfil.USUARIO, eh_o_atribuido=False)


def test_gerenciar_usuarios_somente_gerente():
    assert permissoes.pode_gerenciar_usuarios(Perfil.GERENTE)
    assert not permissoes.pode_gerenciar_usuarios(Perfil.CHEFE)


# ---------------- Fluxo ----------------

def test_fluxo_principal():
    s = Status.NOVA
    s = proximo_status(Acao.ATRIBUIR, s)
    assert s == Status.AGUARDANDO_ACEITE
    s = proximo_status(Acao.ACEITAR, s)
    assert s == Status.EM_ANDAMENTO
    s = proximo_status(Acao.ENVIAR_REVISAO, s)
    assert s == Status.EM_REVISAO
    s = proximo_status(Acao.APROVAR, s)
    assert s == Status.CONCLUIDA


def test_nao_aprova_sem_revisao():
    with pytest.raises(TransicaoInvalida):
        proximo_status(Acao.APROVAR, Status.EM_ANDAMENTO)


@pytest.mark.parametrize("final", [Status.CONCLUIDA, Status.CANCELADA])
@pytest.mark.parametrize("acao", Acao.TODAS)
def test_status_finais_nao_mudam(final, acao):
    with pytest.raises(TransicaoInvalida):
        proximo_status(acao, final)


def test_recusada_pode_ser_reatribuida():
    assert proximo_status(Acao.ATRIBUIR, Status.RECUSADA) == Status.AGUARDANDO_ACEITE


def test_arraste_permitido_e_bloqueado():
    assert acao_por_arraste(Status.AGUARDANDO_ACEITE, Status.EM_ANDAMENTO) == Acao.ACEITAR
    with pytest.raises(TransicaoInvalida):
        acao_por_arraste(Status.NOVA, Status.CONCLUIDA)


def test_gestor_do_plano_tem_os_mesmos_poderes_do_chefe():
    from app.services import permissoes
    from app.services.perfis import Perfil

    for regra in (permissoes.pode_criar_demanda, permissoes.pode_editar_demanda, permissoes.pode_cancelar,
                  permissoes.pode_definir_gut, permissoes.pode_ver_todas, permissoes.pode_gerenciar_usuarios):
        assert regra(Perfil.GESTOR_PLANO) == regra(Perfil.CHEFE), regra.__name__
    for destino in Perfil.TODOS:
        assert permissoes.pode_atribuir(Perfil.GESTOR_PLANO, destino) == permissoes.pode_atribuir(Perfil.CHEFE, destino)
    for eh_o_atribuido in (True, False):
        assert permissoes.pode_revisar(Perfil.GESTOR_PLANO, eh_o_atribuido) == permissoes.pode_revisar(Perfil.CHEFE, eh_o_atribuido)
    assert not permissoes.pode_gerenciar_usuarios(Perfil.GESTOR_PLANO)
    assert not permissoes.pode_atribuir(Perfil.GESTOR_PLANO, Perfil.GERENTE)


def test_gestor_do_plano_pode_atribuir_a_si_mas_nao_aprovar():
    from app.services import permissoes
    from app.services.perfis import Perfil

    assert permissoes.pode_atribuir(Perfil.GESTOR_PLANO, Perfil.GESTOR_PLANO, para_si=True)
    assert not permissoes.pode_atribuir(Perfil.GESTOR_PLANO, Perfil.GESTOR_PLANO)
    assert not permissoes.pode_atribuir(Perfil.CHEFE, Perfil.CHEFE, para_si=True)
    assert not permissoes.pode_revisar(Perfil.GESTOR_PLANO, eh_o_atribuido=True)


def test_padrao_das_permissoes_e_configuracao():
    from app.services import permissoes
    from app.services.perfis import Perfil

    assert permissoes.descrever_atribuicao(Perfil.GERENTE) is None
    assert permissoes.descrever_atribuicao(Perfil.GESTOR_PLANO) == "só pode atribuir a si mesmo ou a usuários com perfil Usuário Comum"
    assert not permissoes.pode_atribuir_alguem(Perfil.USUARIO)

    permissoes.configurar({(Perfil.USUARIO, "atribuir_a_si"): True, (Perfil.GERENTE, "revisar_propria"): False})
    try:
        assert permissoes.pode_atribuir(Perfil.USUARIO, Perfil.USUARIO, para_si=True)
        assert permissoes.pode_atribuir_alguem(Perfil.USUARIO)
        assert not permissoes.pode_revisar(Perfil.GERENTE, eh_o_atribuido=True)
        assert permissoes.pode_revisar(Perfil.GERENTE, eh_o_atribuido=False)
    finally:
        permissoes.configurar({})
