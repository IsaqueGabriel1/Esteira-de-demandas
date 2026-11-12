# Esteira de Demandas — Divisão de Informações de Outorgas

Sistema web para registrar, atribuir, acompanhar e priorizar (Matriz GUT) as demandas da divisão.

**Stack:** Python 3.12 · Flask · PostgreSQL 16 · Jinja2 + jQuery · Bootstrap 5 · Docker
**Arquitetura:** MVC com camada de serviços (regras de negócio isoladas e testadas).

---

## 1. Primeira execução (desenvolvimento)

Pré-requisito: Docker Desktop instalado e aberto.

```bash
# 1. Crie o arquivo de configuração a partir do modelo
copy .env.example .env        # Windows (PowerShell/CMD)
cp .env.example .env          # Linux/macOS

# 2. Edite o .env: troque SECRET_KEY, POSTGRES_PASSWORD, ADMIN_EMAIL e ADMIN_SENHA

# 3. Suba os containers (a primeira vez baixa as imagens e instala as dependências)
docker compose up --build
```

Acesse **http://localhost:8000** e entre com o `ADMIN_EMAIL` / `ADMIN_SENHA` definidos no `.env`.
Esse é o Gerente administrador: pelo menu **Usuários** ele cadastra os demais.

Na inicialização o container executa automaticamente:
1. `flask db upgrade` – cria/atualiza as tabelas;
2. `flask seed` – cadastra os 6 eixos, as divisões padrão e o Gerente administrador (só se ainda não existirem).

Em desenvolvimento o código é montado como volume: ao salvar um arquivo no VS Code, o Flask recarrega sozinho.

## 2. Comandos do dia a dia

| O que fazer | Comando |
|---|---|
| Subir (em segundo plano) | `docker compose up -d` |
| Ver logs | `docker compose logs -f app` |
| Parar | `docker compose down` |
| Rodar os testes | `docker compose exec app pytest` |
| Criar migração após alterar um model | `docker compose exec app flask db migrate -m "descricao"` |
| Aplicar migrações | `docker compose exec app flask db upgrade` |
| Criar usuário pela linha de comando | `docker compose exec app flask criar-usuario --perfil GERENTE` |
| Abrir o banco (psql) | `docker compose exec db psql -U esteira esteira` |
| Apagar tudo, inclusive o banco ⚠️ | `docker compose down -v` |

## 3. Backup e restauração do banco

```bash
# Backup (gera backup.sql na pasta do projeto)
docker compose exec -T db pg_dump -U esteira -d esteira --clean --if-exists > backup.sql

# Restauração
docker compose exec -T db psql -U esteira -d esteira < backup.sql
```

Troque `esteira` pelos valores de `POSTGRES_USER` / `POSTGRES_DB` se tiver alterado o `.env`.

## 4. Produção (servidor interno Linux)

```bash
# No .env: APP_CONFIG=production, SECRET_KEY forte, senhas fortes
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Em produção a aplicação roda com **Gunicorn** atrás do **Nginx** (porta `HTTP_PORT`, padrão 80), que também serve os arquivos estáticos.
Se o acesso for por HTTPS, defina `SESSION_COOKIE_SECURE=true`.
Todas as bibliotecas de interface (Bootstrap, jQuery, Select2, SortableJS, Chart.js, Bootstrap Icons) estão em `app/static/vendor/`, então o sistema **não depende de acesso à internet** para funcionar.

> Se a rede da agência usar proxy para acessar a internet, o `docker compose build` pode precisar das variáveis `HTTP_PROXY`/`HTTPS_PROXY` para baixar as dependências Python.

---

## 5. Regras de negócio

### Perfis
| Ação | Gerente | Chefe de Divisão / Gestor do Plano | Usuário Comum |
|---|---|---|---|
| Criar / editar / cancelar demanda | ✅ | ✅ | ❌ |
| Definir pesos GUT | ✅ | ✅ | ❌ |
| Atribuir demanda | a qualquer pessoa | **só a Usuário Comum** | ❌ |
| Aceitar / recusar (recusa exige justificativa) | se for o atribuído | se for o atribuído | se for o atribuído |
| Enviar para revisão | se for o atribuído | se for o atribuído | se for o atribuído |
| Aprovar / devolver entrega | ✅ | ✅ (exceto a própria) | ❌ |
| Ver demandas | todas | todas | só as suas e as de apoio |
| Gerenciar usuários | ✅ | ❌ | ❌ |
| Gerenciar divisões | só o Administrador¹ | ❌ | ❌ |

O perfil **Gestor do Plano** tem os mesmos poderes do Chefe de Divisão e, além disso, pode atribuir demandas **a si mesmo** (aceite automático). Como qualquer gestor, não pode aprovar a própria entrega.

¹ O **Administrador** é a conta do `ADMIN_EMAIL` do `.env` (não qualquer Gerente).

A tabela acima é o **padrão**. O Administrador pode ligar/desligar cada funcionalidade por perfil no menu **Permissões** (inclusive a quem cada perfil pode atribuir e se pode aprovar a própria entrega); "Restaurar padrão" desfaz tudo e cada alteração fica registrada. Aceitar, recusar e enviar para revisão continuam sempre com o atribuído, e só o Administrador acessa a tela de Permissões e a de Divisões.

O campo "Usuário atribuído" lista todos os usuários; os que o perfil logado não pode atribuir aparecem desabilitados, e a regra é **validada novamente no back-end** (`app/services/permissoes.py`).

### Fluxo da demanda
```
A atribuir → Aguardando aceite → Não iniciada → Em andamento → Em validação → Concluída

Aguardando aceite → Recusada (justificativa) → reatribuir → Aguardando aceite
Em validação → devolver (motivo) → Em andamento
Qualquer status não final → cancelar (motivo) → Cancelada
```
- Gestor que atribui a demanda a si mesmo já fica "Não iniciada" (aceite automático).
- Recusada volta para quem atribuiu (aparece em **Minhas demandas › Recusadas**).
- Demanda não finalizada com prazo vencido é destacada como **Atrasada**. O prazo é o **Prazo acordado** (definido pelo responsável na tela da demanda) ou, se ele estiver vazio, a data de término.
- No quadro, arrastar o card só é permitido para: aceitar, iniciar, enviar para revisão e aprovar, sempre uma etapa por vez. Ações que pedem texto (recusar, devolver, cancelar, atribuir) ficam na tela da demanda.

### Divisões
- Cadastradas pelo Administrador no menu **Divisões**. Cada divisão indica onde aparece: no **cadastro de usuários** (criação de conta, Usuários e "Minha divisão") e/ou nas **demandas** (criação e edição).
- Padrão: DIO, DPO e GGO em ambos; SR só para usuários; DIO/DPO, DPO/DIO e GGO/DPO/DIO só nas demandas.
- A sigla não pode ser alterada nem excluída, pois usuários e demandas a guardam como texto. Uma divisão **inativa** some das opções, mas quem já a usa continua com ela.

### Matriz GUT
- G, U e T: inteiros de 1 a 5. **P = G × U × T** (1 a 125), calculado pelo sistema.
- Faixas: **Baixa** 1–27 · **Média** 28–63 · **Alta** 64–125 (ajustáveis em `app/services/gut.py`).
- Sem os três pesos: "Aguardando priorização" (fica por último na ordenação).
- Toda alteração de pesos é registrada no histórico com valores antigos e novos.

---

## 6. Estrutura do projeto

```
app/
  __init__.py          # create_app (application factory)
  extensions.py        # db, migrate, login_manager, csrf
  cli.py               # comandos: flask seed, flask criar-usuario
  models/              # M — Usuario, Eixo, Divisao, Demanda, HistoricoDemanda
  services/            # regras de negócio
    permissoes.py      #   matriz de permissões (puro)
    fluxo.py           #   máquina de estados (puro)
    gut.py             #   cálculo e faixas GUT (puro)
    demanda_service.py #   criação, atribuição, fluxo, consultas
    divisao_service.py #   cadastro de divisões e opções dos formulários
    usuario_service.py, indicadores_service.py, exportacao_service.py
  controllers/         # C — blueprints: auth, demandas, usuarios, divisoes, indicadores
  forms/               # Flask-WTF (validação + CSRF)
  templates/           # V — Jinja2
  static/              # css, js e vendor/ (bibliotecas locais)
migrations/            # Alembic
tests/                 # pytest (SQLite em memória)
docker/entrypoint.sh   # migrações + seed na inicialização
```

## 7. Rodar sem Docker (opcional)

```bash
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements-dev.txt
pytest                                           # testes usam SQLite em memória
set FLASK_APP=wsgi.py && flask db upgrade && flask seed && flask run --debug
```
Sem `DATABASE_URL`, a aplicação usa um arquivo SQLite local (`dev.db`).
