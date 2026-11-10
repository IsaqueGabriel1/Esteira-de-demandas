"""Regras de negócio das demandas, com banco (SQLite em memória)."""
from datetime import date, timedelta

import pytest

from app.models import TipoEvento
from app.services import demanda_service as svc
from app.services.erros import PermissaoNegada, RegraNegocioError
from app.services.fluxo import Status


# ---------------- Criação ----------------

def test_gerente_e_chefe_criam_usuario_nao(usuarios, nova_demanda):
    assert nova_demanda(usuarios["gerente"]).status == Status.NOVA
    assert nova_demanda(usuarios["chefe"]).status == Status.NOVA
    with pytest.raises(PermissaoNegada):
        nova_demanda(usuarios["usuario"])


def test_campos_obrigatorios(usuarios, nova_demanda):
    with pytest.raises(RegraNegocioError):
        nova_demanda(usuarios["gerente"], acao="   ")
    with pytest.raises(RegraNegocioError):
        nova_demanda(usuarios["gerente"], produto="")
    with pytest.raises(RegraNegocioError):
        nova_demanda(usuarios["gerente"], eixo_id=9999)


def test_termino_antes_do_inicio_e_rejeitado(usuarios, nova_demanda):
    with pytest.raises(RegraNegocioError):
        nova_demanda(usuarios["gerente"], inicio=date(2026, 5, 10), termino=date(2026, 5, 1))


def test_criacao_registra_historico(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"])
    assert [h.tipo for h in d.historico] == [TipoEvento.CRIACAO]


def test_criacao_com_gut_calcula_prioridade(usuarios, nova_demanda):
    d = nova_demanda(usuarios["chefe"], gravidade=5, urgencia=4, tendencia=3)
    assert d.prioridade == 60
    assert d.faixa[1] == "media"


def test_gut_incompleto_e_rejeitado(usuarios, nova_demanda):
    with pytest.raises(RegraNegocioError):
        nova_demanda(usuarios["gerente"], gravidade=5, urgencia=None, tendencia=3)


# ---------------- Atribuição ----------------

def test_gerente_atribui_a_chefe(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["chefe"].id)
    assert d.status == Status.AGUARDANDO_ACEITE
    assert d.atribuido_id == usuarios["chefe"].id
    assert d.atribuido_por_id == usuarios["gerente"].id


def test_chefe_nao_atribui_a_gerente_nem_a_outro_chefe(usuarios, nova_demanda):
    with pytest.raises(PermissaoNegada):
        nova_demanda(usuarios["chefe"], atribuido_id=usuarios["gerente"].id)
    with pytest.raises(PermissaoNegada):
        nova_demanda(usuarios["chefe"], atribuido_id=usuarios["chefe2"].id)


def test_chefe_nao_reatribui_a_chefe(db, usuarios, nova_demanda):
    d = nova_demanda(usuarios["chefe"])
    with pytest.raises(PermissaoNegada):
        svc.atribuir(usuarios["chefe"], d, usuarios["chefe2"].id)
    db.session.rollback()
    svc.atribuir(usuarios["chefe"], d, usuarios["usuario"].id)
    assert d.status == Status.AGUARDANDO_ACEITE


def test_usuario_comum_nao_atribui(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"])
    with pytest.raises(PermissaoNegada):
        svc.atribuir(usuarios["usuario"], d, usuarios["usuario2"].id)


def test_gerente_atribuindo_a_si_mesmo_aceita_automaticamente(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["gerente"].id)
    assert d.status == Status.EM_ANDAMENTO


# ---------------- Aceite e recusa ----------------

def test_somente_o_atribuido_aceita(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    with pytest.raises(PermissaoNegada):
        svc.aceitar(usuarios["usuario2"], d)
    svc.aceitar(usuarios["usuario"], d)
    assert d.status == Status.EM_ANDAMENTO


def test_recusa_exige_justificativa(usuarios, nova_demanda):
    d = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id)
    with pytest.raises(RegraNegocioError):
        svc.recusar(usuarios["usuario"], d, "")
    with pytest.raises(RegraNegocioError):
        svc.recusar(usuarios["usuario"], d, "não")
    assert d.status == Status.AGUARDANDO_ACEITE


def test_recusa_volta_para_quem_atribuiu(usuarios, nova_demanda):
    d = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id)
    svc.recusar(usuarios["usuario"], d, "Estou alocado no relatório anual até sexta.")
    assert d.status == Status.RECUSADA
    assert d.atribuido_id is None
    assert d.recusado_por_id == usuarios["usuario"].id
    assert d.justificativa_recusa.startswith("Estou alocado")
    assert d in svc.minhas(usuarios["chefe"])["recusadas"]
    assert d.historico[0].tipo == TipoEvento.RECUSA

    # Quem recusou continua vendo a demanda (histórico), e ela pode ser reatribuída
    assert svc.pode_ver(usuarios["usuario"], d)
    svc.atribuir(usuarios["chefe"], d, usuarios["usuario2"].id)
    assert d.status == Status.AGUARDANDO_ACEITE
    assert d.justificativa_recusa is None


def test_chefe_atribuido_pelo_gerente_tambem_pode_recusar(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["chefe"].id)
    svc.recusar(usuarios["chefe"], d, "Fora do escopo da minha divisão.")
    assert d.status == Status.RECUSADA


# ---------------- Revisão e conclusão ----------------

def _em_andamento(usuarios, nova_demanda):
    d = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id)
    svc.aceitar(usuarios["usuario"], d)
    return d


def test_fluxo_completo_ate_concluir(usuarios, nova_demanda):
    d = _em_andamento(usuarios, nova_demanda)
    svc.enviar_revisao(usuarios["usuario"], d, "Planilha anexada na pasta da divisão.")
    assert d.status == Status.EM_REVISAO
    with pytest.raises(PermissaoNegada):
        svc.aprovar(usuarios["usuario"], d)
    svc.aprovar(usuarios["chefe"], d)
    assert d.status == Status.CONCLUIDA
    assert d.concluido_em is not None


def test_devolucao_exige_motivo_e_volta_para_andamento(usuarios, nova_demanda):
    d = _em_andamento(usuarios, nova_demanda)
    svc.enviar_revisao(usuarios["usuario"], d)
    with pytest.raises(RegraNegocioError):
        svc.devolver(usuarios["chefe"], d, "")
    svc.devolver(usuarios["chefe"], d, "Faltou a coluna de vazão outorgada.")
    assert d.status == Status.EM_ANDAMENTO


def test_chefe_nao_aprova_a_propria_entrega(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["chefe"].id)
    svc.aceitar(usuarios["chefe"], d)
    svc.enviar_revisao(usuarios["chefe"], d)
    with pytest.raises(PermissaoNegada):
        svc.aprovar(usuarios["chefe"], d)
    svc.aprovar(usuarios["chefe2"], d)
    assert d.status == Status.CONCLUIDA


def test_concluida_nao_pode_ser_editada(usuarios, nova_demanda, eixo):
    d = _em_andamento(usuarios, nova_demanda)
    svc.enviar_revisao(usuarios["usuario"], d)
    svc.aprovar(usuarios["gerente"], d)
    with pytest.raises(RegraNegocioError):
        svc.editar(usuarios["gerente"], d, {"eixo_id": eixo.id, "acao": "x", "produto": "y", "divisao": "DPO"})
    with pytest.raises(RegraNegocioError):
        svc.definir_gut(usuarios["gerente"], d, 5, 5, 5)


def test_cancelamento(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"])
    with pytest.raises(PermissaoNegada):
        svc.cancelar(usuarios["usuario"], d, "Não precisamos mais disso.")
    with pytest.raises(RegraNegocioError):
        svc.cancelar(usuarios["gerente"], d, "")
    svc.cancelar(usuarios["gerente"], d, "Demanda duplicada da #12.")
    assert d.status == Status.CANCELADA


# ---------------- GUT ----------------

def test_usuario_comum_nao_define_gut(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    with pytest.raises(PermissaoNegada):
        svc.definir_gut(usuarios["usuario"], d, 5, 5, 5)


def test_alteracao_de_gut_fica_no_historico(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], gravidade=2, urgencia=2, tendencia=2)
    svc.definir_gut(usuarios["chefe"], d, 5, 5, 4)
    assert d.prioridade == 100
    evento = d.historico[0]
    assert evento.tipo == TipoEvento.GUT
    assert evento.usuario_id == usuarios["chefe"].id
    assert evento.dados["antes"]["p"] == 8
    assert evento.dados["depois"]["p"] == 100


def test_gut_sem_mudanca_nao_gera_historico(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], gravidade=3, urgencia=3, tendencia=3)
    total = len(d.historico)
    assert svc.definir_gut(usuarios["gerente"], d, 3, 3, 3) is False
    assert len(d.historico) == total


# ---------------- Apoio ----------------

def test_apoio_nao_pode_ser_o_atribuido(usuarios, nova_demanda):
    with pytest.raises(RegraNegocioError):
        nova_demanda(
            usuarios["gerente"], atribuido_id=usuarios["usuario"].id, apoio_ids=[usuarios["usuario"].id]
        )


def test_apoio_ve_a_demanda(usuarios, nova_demanda):
    d = nova_demanda(
        usuarios["gerente"], atribuido_id=usuarios["usuario"].id, apoio_ids=[usuarios["usuario2"].id]
    )
    assert svc.pode_ver(usuarios["usuario2"], d)
    assert d in svc.minhas(usuarios["usuario2"])["apoio"]


# ---------------- Visibilidade, ordenação e filtros ----------------

def test_usuario_comum_so_ve_as_suas(usuarios, nova_demanda):
    minha = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    alheia = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario2"].id)
    visiveis = svc.consultar(usuarios["usuario"]).all()
    assert minha in visiveis and alheia not in visiveis
    with pytest.raises(PermissaoNegada):
        svc.obter(usuarios["usuario"], alheia.id)
    assert len(svc.consultar(usuarios["chefe"]).all()) == 2


def test_ordenacao_por_prioridade_com_sem_gut_por_ultimo(usuarios, nova_demanda):
    baixa = nova_demanda(usuarios["gerente"], gravidade=1, urgencia=2, tendencia=1)
    sem_gut = nova_demanda(usuarios["gerente"])
    alta = nova_demanda(usuarios["gerente"], gravidade=5, urgencia=5, tendencia=4)
    assert svc.consultar(usuarios["gerente"]).all() == [alta, baixa, sem_gut]


def test_filtros(usuarios, nova_demanda):
    ontem = date.today() - timedelta(days=1)
    atrasada = nova_demanda(usuarios["gerente"], termino=ontem, gravidade=5, urgencia=5, tendencia=5)
    nova_demanda(usuarios["gerente"], acao="Tratar base de captações")
    assert svc.consultar(usuarios["gerente"], {"atrasadas": True}).all() == [atrasada]
    assert svc.consultar(usuarios["gerente"], {"faixa": "alta"}).all() == [atrasada]
    assert len(svc.consultar(usuarios["gerente"], {"busca": "captações"}).all()) == 1
    assert svc.consultar(usuarios["gerente"], {"busca": f"#{atrasada.id}"}).all() == [atrasada]
    assert atrasada.atrasada


def test_quadro_agrupa_por_status(usuarios, nova_demanda):
    nova_demanda(usuarios["gerente"])
    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    colunas = svc.quadro(usuarios["gerente"])
    assert len(colunas[Status.NOVA]) == 1
    assert len(colunas[Status.AGUARDANDO_ACEITE]) == 1


# ---------------- Arrastar e soltar ----------------

def test_arraste_valida_permissao(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    with pytest.raises(PermissaoNegada):
        svc.mover_por_arraste(usuarios["usuario2"], d, Status.EM_ANDAMENTO)
    svc.mover_por_arraste(usuarios["usuario"], d, Status.EM_ANDAMENTO)
    assert d.status == Status.EM_ANDAMENTO
    with pytest.raises(RegraNegocioError):
        svc.mover_por_arraste(usuarios["usuario"], d, Status.CONCLUIDA)


def test_divisao_e_obrigatoria_e_registrada_na_edicao(usuarios, nova_demanda, eixo):
    from app.services import demanda_service as svc
    from app.services.erros import RegraNegocioError

    with pytest.raises(RegraNegocioError):
        nova_demanda(usuarios["gerente"], divisao="")
    with pytest.raises(RegraNegocioError):
        nova_demanda(usuarios["gerente"], divisao="OUTRA")

    d = nova_demanda(usuarios["gerente"], divisao="DIO")
    svc.editar(usuarios["gerente"], d, {"eixo_id": eixo.id, "acao": d.acao, "produto": d.produto, "divisao": "DIO/DPO"})
    assert d.divisao == "DIO/DPO"
    assert any("divisão: DIO → DIO/DPO" in h.descricao for h in d.historico)


@pytest.mark.parametrize("divisao", ["DIO", "DPO", "GGO", "DIO/DPO", "DPO/DIO", "GGO/DPO/DIO"])
def test_todas_as_divisoes_sao_aceitas(usuarios, nova_demanda, divisao):
    d = nova_demanda(usuarios["gerente"], divisao=divisao)
    assert d.divisao == divisao


def test_pasta_da_rede_e_opcional_e_registrada_na_edicao(usuarios, nova_demanda, eixo):
    from app.services import demanda_service as svc

    d = nova_demanda(usuarios["gerente"], pasta_rede="   ")
    assert d.pasta_rede is None

    caminho = r"\servidor\outorgas\inventario"
    svc.editar(usuarios["gerente"], d, {"eixo_id": eixo.id, "acao": d.acao, "produto": d.produto,
                                         "divisao": d.divisao, "pasta_rede": caminho})
    assert d.pasta_rede == caminho
    assert any("pasta da rede" in h.descricao for h in d.historico)


def test_regras_do_cadastro_de_divisoes(app, db, usuarios):
    from app.models import Usuario
    from app.services import divisao_service as svc
    from app.services.erros import PermissaoNegada, RegraNegocioError

    with pytest.raises(PermissaoNegada):
        svc.criar(usuarios["gerente"], "NOVA")  # Gerente comum não é o Administrador

    admin = Usuario(nome="Administrador", email=app.config["ADMIN_EMAIL"], perfil="GERENTE", ativo=True)
    admin.definir_senha("senha-segura-123")
    db.session.add(admin)
    db.session.commit()

    nova = svc.criar(admin, "  nova  sigla ", para_usuarios=False, para_demandas=True)
    assert nova.sigla == "NOVA SIGLA"
    assert "NOVA SIGLA" in svc.siglas_para_demandas() and "NOVA SIGLA" not in svc.siglas_para_usuarios()

    with pytest.raises(RegraNegocioError):
        svc.criar(admin, "nova sigla")  # duplicada
    with pytest.raises(RegraNegocioError):
        svc.criar(admin, "")
    with pytest.raises(RegraNegocioError):
        svc.criar(admin, "X" * 21)
    with pytest.raises(RegraNegocioError):
        svc.criar(admin, "SEM USO", para_usuarios=False, para_demandas=False)

    svc.atualizar(admin, nova, para_usuarios=False, para_demandas=True, ativa=False)
    assert "NOVA SIGLA" not in svc.siglas_para_demandas()
    assert "NOVA SIGLA" in svc.siglas_para_demandas(atual="NOVA SIGLA")
