"""Testes das rotas (controllers + templates)."""
from app.services.fluxo import Status


def test_paginas_exigem_login(client):
    resposta = client.get("/quadro")
    assert resposta.status_code == 302
    assert "/login" in resposta.headers["Location"]


def test_login_invalido(client, usuarios):
    resposta = client.post("/login", data={"email": usuarios["gerente"].email, "senha": "errada"})
    assert "E-mail ou senha inválidos".encode() in resposta.data


def test_telas_principais_renderizam(client, login, usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id, gravidade=4, urgencia=4, tendencia=4)
    login(usuarios["gerente"])
    for url in ["/quadro", "/demandas", "/minhas", "/indicadores/", "/usuarios/", "/demandas/nova",
                f"/demandas/{d.id}", f"/demandas/{d.id}/editar", "/minha-senha"]:
        resposta = client.get(url)
        assert resposta.status_code == 200, url


def test_exportacao_csv(client, login, usuarios, nova_demanda):
    nova_demanda(usuarios["gerente"], acao="Relatório de outorgas vencidas")
    login(usuarios["gerente"])
    resposta = client.get("/demandas?formato=csv")
    assert resposta.status_code == 200
    assert resposta.mimetype == "text/csv"
    assert "Relatório de outorgas vencidas" in resposta.data.decode("utf-8-sig")


def test_criar_demanda_pelo_formulario(client, login, usuarios, eixo):
    login(usuarios["chefe"])
    resposta = client.post("/demandas/nova", data={
        "eixo_id": eixo.id, "acao": "Criar regra de negócio", "produto": "Documento de regra",
        "atribuido_id": usuarios["usuario"].id, "apoio_ids": [usuarios["usuario2"].id],
        "gravidade": 3, "urgencia": 3, "tendencia": 3,
    })
    assert resposta.status_code == 302
    assert "/demandas/1" in resposta.headers["Location"]


def test_formulario_bloqueia_chefe_atribuindo_a_gerente(client, login, usuarios, eixo):
    login(usuarios["chefe"])
    resposta = client.post("/demandas/nova", data={
        "eixo_id": eixo.id, "acao": "x", "produto": "y", "atribuido_id": usuarios["gerente"].id,
    }, follow_redirects=True)
    assert "só pode atribuir".encode() in resposta.data


def test_usuario_comum_nao_cria_nem_gerencia_usuarios(client, login, usuarios):
    login(usuarios["usuario"])
    assert client.get("/demandas/nova").status_code == 403
    assert client.get("/usuarios/").status_code == 403


def test_usuario_nao_ve_demanda_alheia(client, login, usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario2"].id)
    login(usuarios["usuario"])
    assert client.get(f"/demandas/{d.id}").status_code == 403


def test_recusa_pela_tela(client, login, usuarios, nova_demanda):
    d = nova_demanda(usuarios["chefe"], atribuido_id=usuarios["usuario"].id)
    login(usuarios["usuario"])
    client.post(f"/demandas/{d.id}/acao/recusar", data={"texto": "curto"})
    assert d.status == Status.AGUARDANDO_ACEITE
    client.post(f"/demandas/{d.id}/acao/recusar", data={"texto": "Sem acesso à base necessária."})
    assert d.status == Status.RECUSADA


def test_mover_no_quadro(client, login, usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    login(usuarios["usuario"])
    resposta = client.post(f"/demandas/{d.id}/mover", json={"status": Status.CONCLUIDA})
    assert resposta.status_code == 422 and resposta.json["ok"] is False
    resposta = client.post(f"/demandas/{d.id}/mover", json={"status": Status.EM_ANDAMENTO})
    assert resposta.status_code == 200 and resposta.json["status"] == Status.EM_ANDAMENTO


def test_gerente_cria_usuario(client, login, usuarios):
    login(usuarios["gerente"])
    resposta = client.post("/usuarios/novo", data={
        "nome": "Nova Pessoa", "email": "nova@teste.gov.br", "perfil": "USUARIO", "senha": "senha-forte-1", "ativo": "y",
    })
    assert resposta.status_code == 302
    from app.models import Usuario
    assert Usuario.query.filter_by(email="nova@teste.gov.br").first() is not None


def test_nao_desativa_ultimo_gerente(client, login, usuarios):
    from app.services import usuario_service
    from app.services.erros import RegraNegocioError
    import pytest

    g = usuarios["gerente"]
    with pytest.raises(RegraNegocioError):
        usuario_service.atualizar(g, g, g.nome, g.email, "CHEFE", ativo=True)
