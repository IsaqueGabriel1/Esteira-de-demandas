"""Carga inicial das demandas do Plano de Trabalho."""
import pytest

from app.models import Demanda, HistoricoDemanda, TipoEvento
from app.services import carga_inicial
from app.services.erros import RegraNegocioError
from app.services.fluxo import Status


def test_arquivo_do_plano_e_valido(app):
    linhas = carga_inicial.ler_plano()
    assert len(linhas) == 53
    carga_inicial._validar(linhas)  # não levanta erro


def test_carrega_todas_as_demandas_como_novas(usuarios):
    gerente = usuarios["gerente"]
    assert carga_inicial.carregar_plano_trabalho(gerente) == 53

    demandas = Demanda.query.all()
    assert len(demandas) == 53
    assert {d.status for d in demandas} == {Status.NOVA}
    assert {d.criado_por_id for d in demandas} == {gerente.id}
    assert HistoricoDemanda.query.filter_by(tipo=TipoEvento.CRIACAO).count() == 53

    primeira = Demanda.query.order_by(Demanda.id).first()
    assert primeira.eixo.numero == 1
    assert primeira.acao == "Diagnosticar as fontes e as condições atuais de utilização do balanço hídrico"
    assert primeira.divisao == "DIO"


def test_nao_carrega_de_novo(usuarios):
    carga_inicial.carregar_plano_trabalho(usuarios["gerente"])
    assert carga_inicial.carregar_plano_trabalho(usuarios["gerente"]) == 0
    assert Demanda.query.count() == 53


def test_nao_carrega_se_ja_existem_demandas(usuarios, nova_demanda):
    nova_demanda(usuarios["gerente"])
    assert carga_inicial.carregar_plano_trabalho(usuarios["gerente"]) == 0
    assert Demanda.query.count() == 1


def test_arquivo_com_erro_nao_grava_nada(usuarios, tmp_path):
    arquivo = tmp_path / "plano.csv"
    arquivo.write_text(
        "eixo;acao;produto;divisao\n1;Ação boa;Produto;DIO\n9;Ação ruim;Produto;XYZ\n", encoding="utf-8"
    )
    with pytest.raises(RegraNegocioError) as erro:
        carga_inicial.carregar_plano_trabalho(usuarios["gerente"], arquivo)
    assert "linha 3" in str(erro.value)
    assert Demanda.query.count() == 0


def test_comando_seed_cria_gerente_e_plano(app):
    from app.models import Usuario

    app.config.update(ADMIN_NOME="Admin", ADMIN_EMAIL="admin@teste.gov.br", ADMIN_SENHA="senha-segura-123")
    resultado = app.test_cli_runner().invoke(args=["seed"])
    assert resultado.exit_code == 0, resultado.output
    assert "53 demanda(s) criada(s)" in resultado.output
    assert Usuario.query.filter_by(email="admin@teste.gov.br").count() == 1

    resultado = app.test_cli_runner().invoke(args=["seed"])
    assert "nada a fazer" in resultado.output
    assert Demanda.query.count() == 53
