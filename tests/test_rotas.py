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
        "eixo_id": eixo.id, "acao": "Criar regra de negócio", "produto": "Documento de regra", "divisao": "DIO/DPO",
        "atribuido_id": usuarios["usuario"].id, "apoio_ids": [usuarios["usuario2"].id],
        "gravidade": 3, "urgencia": 3, "tendencia": 3, "termino": "2030-12-31",
    })
    assert resposta.status_code == 302
    assert "/demandas/1" in resposta.headers["Location"]


def test_formulario_bloqueia_chefe_atribuindo_a_gerente(client, login, usuarios, eixo):
    login(usuarios["chefe"])
    resposta = client.post("/demandas/nova", data={
        "eixo_id": eixo.id, "acao": "x", "produto": "y", "divisao": "DIO", "atribuido_id": usuarios["gerente"].id,
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
    assert resposta.status_code == 422  # não pula "Não iniciada"
    resposta = client.post(f"/demandas/{d.id}/mover", json={"status": Status.NAO_INICIADA})
    assert resposta.status_code == 200 and resposta.json["status"] == Status.NAO_INICIADA


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


def test_autocadastro_entra_direto_como_usuario_comum(client, usuarios):
    from app.models import Usuario
    from app.services.perfis import Perfil

    assert client.get("/cadastro").status_code == 200
    resposta = client.post("/cadastro", data={
        "nome": "Nina Nova", "email": "Nova@Teste.gov.br", "divisao": "GGO", "senha": "senha-segura-123", "confirmacao": "senha-segura-123",
    })
    assert resposta.status_code == 302
    novo = Usuario.query.filter_by(email="nova@teste.gov.br").one()
    assert novo.perfil == Perfil.USUARIO and novo.ativo and novo.divisao == "GGO"

    assert "/quadro" in resposta.headers["Location"]
    assert client.get("/quadro").status_code == 200
    assert client.get("/demandas/nova").status_code == 403  # sem poderes de gestor


def test_autocadastro_rejeita_email_existente(client, usuarios):
    resposta = client.post("/cadastro", data={
        "nome": "Outro", "email": usuarios["gerente"].email, "divisao": "DIO", "senha": "senha-segura-123", "confirmacao": "senha-segura-123",
    })
    assert "Já existe um usuário".encode() in resposta.data


def test_usuario_sem_divisao_e_obrigado_a_informar_ao_entrar(client, login, usuarios, db):
    usuario = usuarios["usuario"]
    usuario.divisao = None
    db.session.commit()

    login(usuario)
    resposta = client.get("/quadro")
    assert resposta.status_code == 302 and "/minha-divisao" in resposta.headers["Location"]

    assert client.post("/minha-divisao", data={"divisao": "XYZ"}).status_code == 200
    assert usuario.divisao is None
    resposta = client.post("/minha-divisao", data={"divisao": "SR"})
    assert resposta.status_code == 302
    assert usuario.divisao == "SR"
    assert client.get("/quadro").status_code == 200


def test_administrador_nao_precisa_de_divisao(app, client, login, db):
    from app.models import Usuario
    from app.services.perfis import Perfil

    admin = Usuario(nome="Administrador", email=app.config["ADMIN_EMAIL"], perfil=Perfil.GERENTE, ativo=True)
    admin.definir_senha("senha-segura-123")
    db.session.add(admin)
    db.session.commit()

    login(admin)
    assert client.get("/quadro").status_code == 200


def test_gerente_define_divisao_do_usuario(client, login, usuarios):
    login(usuarios["gerente"])
    alvo = usuarios["usuario2"]
    resposta = client.post(f"/usuarios/{alvo.id}/editar", data={
        "nome": alvo.nome, "email": alvo.email, "perfil": alvo.perfil, "divisao": "GGO", "ativo": "y",
    })
    assert resposta.status_code == 302
    assert alvo.divisao == "GGO"


# ---------------------------------------------------------------------------
# Divisões (somente o Administrador)
# ---------------------------------------------------------------------------

# O navegador sempre envia os pesos GUT ("0" = em branco)
SEM_GUT = {"gravidade": 0, "urgencia": 0, "tendencia": 0}


def _criar_admin(app, db):
    from app.models import Usuario
    from app.services.perfis import Perfil

    admin = Usuario(nome="Administrador", email=app.config["ADMIN_EMAIL"], perfil=Perfil.GERENTE, ativo=True)
    admin.definir_senha("senha-segura-123")
    db.session.add(admin)
    db.session.commit()
    return admin


def test_somente_administrador_acessa_divisoes(app, db, client, login, usuarios):
    login(usuarios["gerente"])  # Gerente que não é o Administrador
    assert client.get("/divisoes/").status_code == 403
    assert client.post("/divisoes/nova", data={"sigla": "XPTO", "para_usuarios": "y"}).status_code == 403
    assert b"/divisoes/" not in client.get("/quadro").data
    client.post("/logout")

    login(_criar_admin(app, db))
    resposta = client.get("/divisoes/")
    assert resposta.status_code == 200
    assert b"GGO/DPO/DIO" in resposta.data
    assert b"/divisoes/" in client.get("/quadro").data


def test_divisao_nova_aparece_no_cadastro_e_nas_demandas(app, db, client, login, usuarios, eixo):
    from app.models import Demanda

    login(_criar_admin(app, db))
    resposta = client.post("/divisoes/nova", data={"sigla": " sgi ", "para_usuarios": "y", "para_demandas": "y", "ativa": "y"})
    assert resposta.status_code == 302
    assert b'value="SGI"' in client.get("/demandas/nova").data

    resposta = client.post("/demandas/nova", data={"eixo_id": eixo.id, "acao": "x", "produto": "y", "divisao": "SGI", **SEM_GUT})
    assert resposta.status_code == 302
    assert Demanda.query.one().divisao == "SGI"
    client.post("/logout")

    assert b'value="SGI"' in client.get("/cadastro").data
    resposta = client.post("/cadastro", data={
        "nome": "Nova Pessoa", "email": "nova@teste.gov.br", "divisao": "SGI",
        "senha": "senha-segura-123", "confirmacao": "senha-segura-123",
    })
    assert resposta.status_code == 302


def test_divisao_respeita_onde_aparece(app, db, client, login):
    login(_criar_admin(app, db))
    client.post("/divisoes/nova", data={"sigla": "SO-DEMANDA", "para_demandas": "y", "ativa": "y"})
    assert b'value="SO-DEMANDA"' in client.get("/demandas/nova").data
    assert b'value="SO-DEMANDA"' not in client.get("/usuarios/novo").data
    # As combinações padrão são só de demanda; SR é só de usuário
    assert b'value="DIO/DPO"' not in client.get("/usuarios/novo").data
    assert b'value="SR"' not in client.get("/demandas/nova").data


def test_divisao_desativada_some_das_opcoes_mas_permanece_nos_registros(app, db, client, login, usuarios, nova_demanda):
    from app.models import Divisao

    d = nova_demanda(usuarios["gerente"], divisao="DPO/DIO")
    login(_criar_admin(app, db))
    divisao = Divisao.query.filter_by(sigla="DPO/DIO").one()
    resposta = client.post(f"/divisoes/{divisao.id}/editar", data={"para_demandas": "y"})  # sem "ativa"
    assert resposta.status_code == 302 and divisao.ativa is False

    assert b'value="DPO/DIO"' not in client.get("/demandas/nova").data
    # A demanda que já usava a divisão continua editável sem precisar trocá-la
    assert b'value="DPO/DIO"' in client.get(f"/demandas/{d.id}/editar").data
    resposta = client.post(f"/demandas/{d.id}/editar", data={
        "eixo_id": d.eixo_id, "acao": "Ação alterada", "produto": d.produto, "divisao": "DPO/DIO", **SEM_GUT,
    })
    assert resposta.status_code == 302
    assert d.acao == "Ação alterada" and d.divisao == "DPO/DIO"


def _admin(app, db):
    from app.models import Usuario
    from app.services.perfis import Perfil

    admin = Usuario(nome="Administrador", email=app.config["ADMIN_EMAIL"], perfil=Perfil.GERENTE, ativo=True)
    admin.definir_senha("senha-segura-123")
    db.session.add(admin)
    db.session.commit()
    return admin


def test_tela_de_permissoes_so_para_o_administrador(app, db, client, login, usuarios):
    login(usuarios["gerente"])
    assert client.get("/permissoes/").status_code == 403
    assert client.post("/permissoes/", data={}).status_code == 403
    assert b"/permissoes/" not in client.get("/quadro").data

    client.post("/logout")
    login(_admin(app, db))
    resposta = client.get("/permissoes/")
    assert resposta.status_code == 200
    assert "Atribuir a Usuário Comum".encode() in resposta.data


def test_desligar_criar_demanda_bloqueia_o_chefe(app, db, client, login, usuarios):
    from app.models import HistoricoPermissao
    from app.services import permissao_service, permissoes
    from app.services.perfis import Perfil

    admin = _admin(app, db)
    ativas = {k for k, v in permissao_service.matriz().items() if v} - {(Perfil.CHEFE, "criar_demanda")}
    login(admin)
    client.post("/permissoes/", data={"ativa": [f"{p}:{c}" for p, c in ativas]})
    assert HistoricoPermissao.query.count() == 1
    client.post("/logout")

    login(usuarios["chefe"])
    assert client.get("/demandas/nova").status_code == 403
    client.post("/logout")
    login(usuarios["gerente"])
    assert client.get("/demandas/nova").status_code == 200

    permissao_service.restaurar_padrao(admin)
    assert permissoes.pode_criar_demanda(Perfil.CHEFE)


def test_prazo_acordado_pela_tela_da_demanda(client, login, usuarios, nova_demanda):
    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    login(usuarios["gerente"])
    assert b'name="prazo_acordado"' not in client.get(f"/demandas/{d.id}").data
    client.post(f"/demandas/{d.id}/prazo-acordado", data={"prazo_acordado": "2030-01-15"})
    assert d.prazo_acordado is None
    client.post("/logout")

    login(usuarios["usuario"])
    assert b'name="prazo_acordado"' in client.get(f"/demandas/{d.id}").data
    resposta = client.post(f"/demandas/{d.id}/prazo-acordado", data={"prazo_acordado": "2030-01-15"})
    assert resposta.status_code == 302
    assert d.prazo_acordado.isoformat() == "2030-01-15"


def test_usuario_comum_nao_tem_minhas_demandas(client, login, usuarios):
    login(usuarios["usuario"])
    assert b'href="/minhas"' not in client.get("/quadro").data
    resposta = client.get("/minhas")
    assert resposta.status_code == 302 and "/quadro" in resposta.headers["Location"]
    client.post("/logout")

    login(usuarios["chefe"])
    assert b'href="/minhas"' in client.get("/quadro").data
    assert client.get("/minhas").status_code == 200


def test_filtros_dos_indicadores(client, login, usuarios, nova_demanda):
    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id, divisao="DPO")
    login(usuarios["gerente"])
    resposta = client.get(f"/indicadores/?usuario={usuarios['usuario'].id}&divisao=DPO")
    assert resposta.status_code == 200
    assert b'name="usuario"' in resposta.data and b'name="divisao"' in resposta.data
    client.post("/logout")

    login(usuarios["usuario"])
    resposta = client.get(f"/indicadores/?usuario={usuarios['usuario2'].id}")
    assert resposta.status_code == 200
    assert b'name="usuario"' not in resposta.data  # só vê as próprias demandas

def test_quadro_e_lista_filtram_pela_divisao_do_responsavel(client, login, usuarios, nova_demanda, db):
    usuarios["usuario"].divisao, usuarios["usuario2"].divisao = "GGO", "SR"
    db.session.commit()
    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id, acao="Tarefa da GGO", divisao="DIO")
    nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario2"].id, acao="Tarefa da SR", divisao="DIO")
    login(usuarios["gerente"])
    for url in ("/quadro", "/demandas"):
        resposta = client.get(f"{url}?divisao=GGO")
        assert b'name="divisao"' in resposta.data
        assert "Tarefa da GGO".encode() in resposta.data and "Tarefa da SR".encode() not in resposta.data

def test_usuario_comum_nao_ve_contagem_de_tempo(client, login, usuarios, nova_demanda):
    from app.services import demanda_service

    d = nova_demanda(usuarios["gerente"], atribuido_id=usuarios["usuario"].id)
    demanda_service.aceitar(usuarios["usuario"], d)
    demanda_service.iniciar(usuarios["usuario"], d)
    login(usuarios["usuario"])
    assert "nesta etapa" not in client.get("/quadro").get_data(as_text=True)
    assert "Em execução há" not in client.get(f"/demandas/{d.id}").get_data(as_text=True)
    assert ">Execução</th>" not in client.get("/demandas").get_data(as_text=True)
    client.post("/logout")

    login(usuarios["gerente"])
    assert "nesta etapa" in client.get("/quadro").get_data(as_text=True)
    assert "Em execução há" in client.get(f"/demandas/{d.id}").get_data(as_text=True)
    lista = client.get("/demandas").get_data(as_text=True)
    assert ">Execução</th>" in lista and "(em curso)" in lista
