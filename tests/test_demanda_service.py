"""Regras de negócio das demandas, com banco (SQLite em memória)."""
from datetime import date, timedelta

import pytest

from app.models import TipoEvento
from app.services import demanda_service as svc
from app.services.erros import PermissaoNegada, RegraNegocioError
from app.services.fluxo import Acao, Status


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
    assert d.faixa[1] == "alta"


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
    d = nova_demanda(usuarios["chefe"], termino=date.today(), gravidade=3, urgencia=3, tendencia=3)
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
    assert d.status == Status.NAO_INICIADA


# ---------------- Aceite e recusa ----------------

def test_somente_o_atribuido_aceita(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    with pytest.raises(PermissaoNegada):
        svc.aceitar(usuarios["usuario2"], d)
    svc.aceitar(usuarios["usuario"], d)
    assert d.status == Status.NAO_INICIADA


def test_somente_o_atribuido_inicia(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    with pytest.raises(RegraNegocioError):
        svc.iniciar(usuarios["usuario"], d)  # precisa aceitar antes
    svc.aceitar(usuarios["usuario"], d)
    assert Acao.INICIAR in svc.acoes_disponiveis(usuarios["usuario"], d)
    with pytest.raises(PermissaoNegada):
        svc.iniciar(usuarios["usuario2"], d)
    with pytest.raises(RegraNegocioError):
        svc.enviar_revisao(usuarios["usuario"], d)  # não pula etapa
    svc.iniciar(usuarios["usuario"], d)
    assert d.status == Status.EM_ANDAMENTO
    assert d.historico[0].tipo == TipoEvento.INICIO


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
    svc.iniciar(usuarios["usuario"], d)
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
    svc.iniciar(usuarios["chefe"], d)
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


def test_quadro_oculta_coluna_a_atribuir_do_usuario_comum(usuarios):
    assert Status.NOVA not in svc.quadro(usuarios["usuario"])
    assert Status.NOVA in svc.quadro(usuarios["chefe"])


# ---------------- Arrastar e soltar ----------------

def test_arraste_valida_permissao(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    with pytest.raises(PermissaoNegada):
        svc.mover_por_arraste(usuarios["usuario2"], d, Status.NAO_INICIADA)
    with pytest.raises(RegraNegocioError):
        svc.mover_por_arraste(usuarios["usuario"], d, Status.EM_ANDAMENTO)  # não pula etapa
    svc.mover_por_arraste(usuarios["usuario"], d, Status.NAO_INICIADA)
    assert d.status == Status.NAO_INICIADA
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


def test_prazo_acordado_define_o_atraso(usuarios, nova_demanda):
    hoje = date.today()
    d = nova_demanda(
        usuarios["gerente"], atribuido_id=usuarios["usuario"].id,
        inicio=hoje - timedelta(days=10), termino=hoje - timedelta(days=1),
    )
    assert d.atrasada  # sem prazo acordado, vale o término

    svc.definir_prazo_acordado(usuarios["usuario"], d, hoje + timedelta(days=5))
    assert not d.atrasada
    assert svc.consultar(usuarios["gerente"], {"atrasadas": True}).all() == []
    assert any("Prazo acordado" in h.descricao for h in d.historico)

    svc.definir_prazo_acordado(usuarios["usuario"], d, hoje - timedelta(days=2))
    assert d.atrasada
    assert svc.consultar(usuarios["gerente"], {"atrasadas": True}).all() == [d]

    with pytest.raises(RegraNegocioError):
        svc.definir_prazo_acordado(usuarios["usuario"], d, d.inicio - timedelta(days=1))

    svc.definir_prazo_acordado(usuarios["usuario"], d, None)
    assert d.prazo_acordado is None


def test_responsavel_e_apoio_alteram_a_pasta_da_rede(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id, apoio_ids=[usuarios["usuario2"].id])
    assert svc.definir_pasta_rede(usuarios["usuario"], d, r"  \\servidor\outorgas  ")
    assert d.pasta_rede == r"\\servidor\outorgas"
    assert d.historico[0].descricao == "Alterado: pasta da rede."
    assert svc.definir_pasta_rede(usuarios["usuario2"], d, "")
    assert d.pasta_rede is None
    assert not svc.definir_pasta_rede(usuarios["usuario2"], d, "  ")  # nada mudou

    assert not svc.pode_definir_pasta_rede(usuarios["chefe"], d)
    with pytest.raises(PermissaoNegada):
        svc.definir_pasta_rede(usuarios["chefe"], d, "x")
    with pytest.raises(RegraNegocioError):
        svc.definir_pasta_rede(usuarios["usuario"], d, "x" * 501)


def test_somente_o_responsavel_define_o_prazo_acordado(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    for outro in ("gerente", "chefe", "usuario2"):
        assert not svc.pode_definir_prazo_acordado(usuarios[outro], d)
        with pytest.raises(PermissaoNegada):
            svc.definir_prazo_acordado(usuarios[outro], d, date.today())
    assert svc.pode_definir_prazo_acordado(usuarios["usuario"], d)


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


def test_permissoes_configuradas_valem_no_servico(app, db, usuarios, nova_demanda):
    import pytest

    from app.services import demanda_service, permissoes
    from app.services.erros import PermissaoNegada
    from app.services.perfis import Perfil

    # Liga para o Chefe atribuir a outro Chefe e aprovar a própria entrega
    permissoes.configurar({(Perfil.CHEFE, "atribuir_" + Perfil.CHEFE): True, (Perfil.CHEFE, "revisar_propria"): True})
    d = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["chefe2"].id)
    assert d.atribuido_id == usuarios["chefe2"].id
    assert permissoes.pode_revisar(Perfil.CHEFE, eh_o_atribuido=True)

    # Desliga a criação para o Gerente
    permissoes.configurar({(Perfil.GERENTE, "criar_demanda"): False})
    with pytest.raises(PermissaoNegada):
        nova_demanda(usuarios["gerente"])


def test_indicadores_filtram_por_usuario_e_divisao_do_responsavel(usuarios, nova_demanda, db):
    from app.services import indicadores_service

    usuarios["usuario"].divisao = "GGO"
    usuarios["usuario2"].divisao = "SR"
    db.session.commit()
    # A divisão da demanda não importa: vale a do cadastro do responsável
    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id, divisao="DIO")
    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario2"].id, divisao="DIO")
    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id, divisao="DPO")
    nova_demanda(usuarios["gerente"], divisao="DIO")

    def ativas(**filtros):
        return indicadores_service.calcular(usuarios["gerente"], filtros)["totais"]["ativas"]

    assert ativas() == 4
    assert ativas(atribuido_id=usuarios["usuario"].id) == 2
    assert ativas(divisao_responsavel="GGO") == 2
    assert ativas(divisao_responsavel="SR") == 1
    assert ativas(divisao_responsavel="DIO") == 0
    assert ativas(atribuido_id=usuarios["usuario"].id, divisao_responsavel="SR") == 0


def _ciclo_completo(usuarios, nova_demanda, db, dias_por_etapa, termino, concluir_ha_dias=2):
    """Cria e conclui uma demanda, reescrevendo as datas do histórico para durações conhecidas.
    dias_por_etapa: (aguardando aceite, não iniciada, em andamento, em validação)."""
    from app.models.base import agora

    d = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id)
    d.termino = termino  # permite simular demandas antigas, atribuídas antes da exigência de prazo
    db.session.commit()
    svc.aceitar(usuarios["usuario"], d)
    svc.iniciar(usuarios["usuario"], d)
    svc.enviar_revisao(usuarios["usuario"], d)
    svc.aprovar(usuarios["chefe"], d)

    fim = agora() - timedelta(days=concluir_ha_dias)
    momento = fim - timedelta(days=sum(dias_por_etapa))
    eventos = sorted(d.historico, key=lambda h: h.id)
    duracoes = iter(dias_por_etapa)
    for evento in eventos:
        evento.criado_em = momento
        if evento.tipo in (TipoEvento.ATRIBUICAO, TipoEvento.ACEITE, TipoEvento.INICIO, TipoEvento.ENVIO_REVISAO):
            momento += timedelta(days=next(duracoes))
    d.concluido_em = fim
    db.session.commit()
    return d


def test_indicadores_de_prazo_e_tempo_por_etapa(usuarios, nova_demanda, db):
    from app.services import indicadores_service

    hoje = date.today()
    _ciclo_completo(usuarios, nova_demanda, db, (1, 2, 4, 1), termino=hoje)                       # no prazo
    _ciclo_completo(usuarios, nova_demanda, db, (3, 2, 6, 5), termino=hoje - timedelta(days=10))  # atrasada
    _ciclo_completo(usuarios, nova_demanda, db, (1, 1, 1, 1), termino=None)                       # sem prazo

    dp = indicadores_service.calcular(usuarios["gerente"])["desempenho"]
    assert dp["concluidas"] == 3
    assert dp["prazo"]["percentual"] == 50
    assert (dp["prazo"]["no_prazo"], dp["prazo"]["com_prazo"], dp["prazo"]["sem_prazo"]) == (1, 2, 1)

    etapas = {e["rotulo"]: e for e in dp["etapas"]}
    assert round(etapas["Aguardando aceite"]["mediana"]) == 1
    assert round(etapas["Em andamento"]["mediana"]) == 4
    assert round(etapas["Em validação"]["mediana"]) == 1
    assert dp["gargalo"] == "Em andamento"
    assert etapas["Em andamento"]["parcela"] == 39  # 11 de 28 dias

    # Fora do período escolhido, a demanda não entra
    antiga = _ciclo_completo(usuarios, nova_demanda, db, (1, 1, 1, 1), termino=hoje, concluir_ha_dias=60)
    assert indicadores_service.calcular(usuarios["gerente"], periodo="30")["desempenho"]["concluidas"] == 3
    assert indicadores_service.calcular(usuarios["gerente"], periodo="90")["desempenho"]["concluidas"] == 4
    assert antiga.status == Status.CONCLUIDA


def test_fluxo_antigo_sem_inicio_conta_como_em_andamento(usuarios, nova_demanda, db):
    from app.services import tempos

    d = _ciclo_completo(usuarios, nova_demanda, db, (1, 3, 0, 1), termino=None)
    inicio = next(h for h in d.historico if h.tipo == TipoEvento.INICIO)
    db.session.delete(inicio)  # demanda concluída antes de existir "Não iniciada"
    db.session.commit()
    duracoes = tempos.tempo_por_etapa(d)
    assert Status.NAO_INICIADA not in duracoes
    assert round(tempos.dias(duracoes[Status.EM_ANDAMENTO])) == 3


def test_formatar_dias():
    from app.services.indicadores_service import formatar_dias

    assert formatar_dias(None) == "—"
    assert formatar_dias(0.25) == "menos de 1 dia"
    assert formatar_dias(1) == "1 dia"
    assert formatar_dias(3.96) == "3 dias"


def test_taxa_de_devolucao_conta_as_validacoes(usuarios, nova_demanda):
    from app.services import indicadores_service

    d = _em_andamento(usuarios, nova_demanda)  # responsável: usuario
    svc.enviar_revisao(usuarios["usuario"], d)
    svc.devolver(usuarios["chefe"], d, "Faltou a coluna de vazão outorgada.")
    svc.enviar_revisao(usuarios["usuario"], d)
    svc.aprovar(usuarios["chefe"], d)

    outra = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario2"].id)
    svc.aceitar(usuarios["usuario2"], outra)
    svc.iniciar(usuarios["usuario2"], outra)
    svc.enviar_revisao(usuarios["usuario2"], outra)
    svc.aprovar(usuarios["chefe"], outra)

    dv = indicadores_service.calcular(usuarios["gerente"])["desempenho"]["devolucoes"]
    assert (dv["devolucoes"], dv["validacoes"], dv["taxa"]) == (1, 3, 33)
    linhas = {l["nome"]: l for l in dv["por_responsavel"]}
    assert linhas[usuarios["usuario"].nome]["taxa"] == 50
    assert linhas[usuarios["usuario2"].nome]["taxa"] == 0
    assert dv["por_responsavel"][0]["nome"] == usuarios["usuario"].nome  # maior taxa primeiro


def test_carga_ponderada_pela_gut(usuarios, nova_demanda, db):
    from app.services import indicadores_service

    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id, gravidade=5, urgencia=5, tendencia=5)
    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario2"].id, gravidade=2, urgencia=2, tendencia=2)
    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario2"].id, gravidade=2, urgencia=2, tendencia=2)
    sem_gut = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario2"].id)
    # Demanda antiga, atribuída antes da exigência de priorização
    sem_gut.gravidade = sem_gut.urgencia = sem_gut.tendencia = sem_gut.prioridade = None
    db.session.commit()
    nova_demanda(usuarios["gerente"], gravidade=5, urgencia=5, tendencia=5)  # sem responsável

    dados = indicadores_service.calcular(usuarios["gerente"])
    assert dados["ativas_sem_responsavel"] == 1
    carga = dados["carga"]
    assert [(l["nome"], l["pontos"], l["ativas"], l["sem_gut"]) for l in carga] == [
        (usuarios["usuario"].nome, 125, 1, 0),
        (usuarios["usuario2"].nome, 16, 3, 1),
    ]


def test_minhas_do_gestor_do_plano_mostra_revisao_so_da_sua_divisao(usuarios, nova_demanda, db):
    from app.services.perfis import Perfil

    gestor = usuarios["chefe2"]
    gestor.perfil, gestor.divisao = Perfil.GESTOR_PLANO, "DPO"
    db.session.commit()
    demandas = {}
    for divisao in ("DPO", "DIO/DPO", "DIO"):
        d = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id, divisao=divisao)
        svc.aceitar(usuarios["usuario"], d)
        svc.iniciar(usuarios["usuario"], d)
        svc.enviar_revisao(usuarios["usuario"], d)
        demandas[divisao] = d

    revisao = svc.minhas(gestor)["revisao"]
    assert demandas["DPO"] in revisao and demandas["DIO/DPO"] in revisao
    assert demandas["DIO"] not in revisao
    # Só na tela Minhas demandas: o quadro continua mostrando todas
    assert demandas["DIO"] in svc.quadro(gestor)[Status.EM_REVISAO]
    # Os demais gestores continuam vendo todas
    assert demandas["DIO"] in svc.minhas(usuarios["chefe"])["revisao"]

def test_voltar_para_em_andamento_exige_a_permissao(usuarios, nova_demanda):
    from app.services import permissoes
    from app.services.perfis import Perfil

    d = _em_andamento(usuarios, nova_demanda)
    svc.enviar_revisao(usuarios["usuario"], d)
    # Desligada por padrão para todos os perfis
    assert Acao.RETOMAR not in svc.acoes_disponiveis(usuarios["usuario"], d)
    with pytest.raises(PermissaoNegada):
        svc.retomar(usuarios["usuario"], d)

    permissoes.configurar({(Perfil.USUARIO, "voltar_andamento"): True})
    try:
        assert Acao.RETOMAR in svc.acoes_disponiveis(usuarios["usuario"], d)
        # Só vale para demandas que o usuário pode ver
        with pytest.raises(PermissaoNegada):
            svc.retomar(usuarios["usuario2"], d)
        svc.retomar(usuarios["usuario"], d, "Esqueci um anexo.")
    finally:
        permissoes.configurar({})
    assert d.status == Status.EM_ANDAMENTO
    retomada = [h for h in d.historico if h.tipo == TipoEvento.RETOMADA]
    assert len(retomada) == 1 and "Esqueci um anexo." in retomada[0].descricao
    # Não pode voltar se não estiver Em validação
    permissoes.configurar({(Perfil.USUARIO, "voltar_andamento"): True})
    try:
        assert Acao.RETOMAR not in svc.acoes_disponiveis(usuarios["usuario"], d)
    finally:
        permissoes.configurar({})

def test_so_atribui_demanda_com_prazo_e_prioridade(db, usuarios, nova_demanda):
    gut = {"gravidade": 3, "urgencia": 3, "tendencia": 3}
    with pytest.raises(RegraNegocioError, match="prazo"):
        nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id, termino=None)
    db.session.rollback()
    with pytest.raises(RegraNegocioError, match="prioridade"):
        nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id, gravidade=None, urgencia=None, tendencia=None)
    db.session.rollback()

    d = nova_demanda(usuarios["chefe"])
    assert svc.pendencias_para_atribuir(d) == ["preencha o prazo (data de término)", "defina a prioridade (pesos GUT)"]
    with pytest.raises(RegraNegocioError):
        svc.atribuir(usuarios["chefe"], d, usuarios["usuario"].id)
    db.session.rollback()
    svc.definir_gut(usuarios["chefe"], d, **gut)
    with pytest.raises(RegraNegocioError, match="prazo"):
        svc.atribuir(usuarios["chefe"], d, usuarios["usuario"].id)
    db.session.rollback()
    d.termino = date.today()
    db.session.commit()
    svc.atribuir(usuarios["chefe"], d, usuarios["usuario"].id)
    assert d.status == Status.AGUARDANDO_ACEITE

def test_contagem_de_tempo_da_demanda(usuarios, nova_demanda, db):
    from app.models.base import agora
    from app.services import tempos

    d = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id)
    assert tempos.inicio_da_execucao(d) is None and tempos.tempo_de_execucao(d) is None
    svc.aceitar(usuarios["usuario"], d)
    svc.iniciar(usuarios["usuario"], d)
    svc.enviar_revisao(usuarios["usuario"], d)
    # Reescreve as datas: iniciada há 10 dias, enviada para validação há 4
    agora_ = agora()
    for h in d.historico:
        h.criado_em = {
            TipoEvento.INICIO: agora_ - timedelta(days=10),
            TipoEvento.ENVIO_REVISAO: agora_ - timedelta(days=4),
        }.get(h.tipo, agora_ - timedelta(days=12))
    db.session.commit()

    assert round(tempos.dias(tempos.tempo_na_etapa_atual(d))) == 4
    assert round(tempos.dias(tempos.tempo_de_execucao(d))) == 10
    resumo = tempos.resumo(d)
    linhas = {e["rotulo"]: e for e in resumo["etapas"]}
    assert linhas["Em andamento"]["texto"] == "6 dias"
    assert linhas["Em validação"]["atual"] and linhas["Em validação"]["texto"] == "4 dias"
    assert resumo["execucao"] == "10 dias"

    svc.aprovar(usuarios["chefe"], d)
    assert tempos.tempo_na_etapa_atual(d) is None
    assert round(tempos.dias(tempos.tempo_de_execucao(d))) == 10  # para de contar na conclusão

def test_demanda_antiga_em_andamento_sem_inicio_conta_execucao(usuarios, nova_demanda, db):
    from app.services import tempos

    d = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id)
    svc.aceitar(usuarios["usuario"], d)
    d.status = Status.EM_ANDAMENTO  # aceita no fluxo antigo, sem o evento "Início"
    db.session.commit()
    assert tempos.inicio_da_execucao(d) is not None
    assert tempos.resumo(d)["etapas"][-1]["rotulo"] == "Em andamento"


# ---------------- Comentários ----------------

def test_comentarios_na_demanda(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)

    c = svc.comentar(usuarios["usuario"], d, "  Aguardando retorno da DPO.  ")
    assert c.texto == "Aguardando retorno da DPO."
    assert d.historico[0].tipo == TipoEvento.COMENTARIO
    svc.comentar(usuarios["gerente"], d, "Ok, obrigado.")
    assert [x.texto for x in d.comentarios_ativos] == ["Aguardando retorno da DPO.", "Ok, obrigado."]

    with pytest.raises(RegraNegocioError):
        svc.comentar(usuarios["usuario"], d, "   ")
    with pytest.raises(RegraNegocioError):
        svc.comentar(usuarios["usuario"], d, "x" * 4001)
    with pytest.raises(PermissaoNegada):  # não vê a demanda
        svc.comentar(usuarios["usuario2"], d, "Oi")

    # Só o autor edita
    with pytest.raises(PermissaoNegada):
        svc.editar_comentario(usuarios["gerente"], d, c.id, "Outro texto")
    assert svc.editar_comentario(usuarios["usuario"], d, c.id, "Retorno recebido.")
    assert c.editado_em is not None
    assert not svc.editar_comentario(usuarios["usuario"], d, c.id, "Retorno recebido.")

    # O gestor também remove; a remoção é lógica
    svc.remover_comentario(usuarios["gerente"], d, c.id)
    assert c.removido_em is not None
    assert len(d.comentarios_ativos) == 1
    with pytest.raises(RegraNegocioError):
        svc.editar_comentario(usuarios["usuario"], d, c.id, "De novo")


def test_comenta_em_demanda_finalizada(usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"])
    svc.cancelar(usuarios["gerente"], d, "Não é mais necessária.")
    svc.comentar(usuarios["gerente"], d, "Registro após o cancelamento.")
    assert len(d.comentarios_ativos) == 1
