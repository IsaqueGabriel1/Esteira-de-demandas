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
2. `flask seed` – cadastra os 6 eixos, as divisões padrão e o Gerente administrador (só se ainda não existirem) e, se a base ainda não tiver demandas, carrega as demandas do Plano de Trabalho (`app/seed_data/plano_de_trabalho.csv`).

Em desenvolvimento o código é montado como volume: ao salvar um arquivo no VS Code, o Flask recarrega sozinho.

### Projeto em pasta de rede (ex.: drive `Y:`)

O Docker Desktop não monta pastas de rede como volume (o container falha com `cannot open /app/docker/entrypoint.sh`). Nesse caso, suba usando o código copiado na imagem:

```bash
docker compose -f docker-compose.yml -f docker-compose.rede.yml up -d --build
```

Não há recarga automática: após alterar o código, rode o mesmo comando de novo (o `atualiza_app.bat` faz isso; ajuste o caminho dentro dele). Neste modo o banco fica acessível só na própria máquina, em `localhost:5434` (DBeaver/pgAdmin). Os dados do banco ficam no volume `pgdata` e são preservados (só `docker compose down -v` os apaga).

## 2. Comandos do dia a dia

| O que fazer | Comando |
|---|---|
| Subir (em segundo plano) | `docker compose up -d` |
| Ver logs | `docker compose logs -f app` |
| Parar | `docker compose down` |
| Rodar os testes | `docker compose exec app pytest` (no modo pasta de rede a imagem não tem o pytest: rode `pip install -r requirements-dev.txt` dentro do container antes, ou rode sem Docker, seção 7) |
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

### Backup automático diário (Windows)

O script `backup_banco.ps1` gera um `pg_dump` compactado em `backups\esteira_AAAA-MM-DD_HHMM.dump`, apaga os arquivos com mais de 30 dias e registra cada execução em `backups\backup.log`. A pasta `backups/` não vai para o git.

Ele está agendado no **Agendador de Tarefas** do Windows como "Esteira de Demandas - Backup do banco", todos os dias às **18h**. Se o computador estiver desligado nesse horário, roda assim que ligar. O Docker Desktop precisa estar aberto. Para recriar o agendamento em outra máquina (PowerShell):

```powershell
$script = "\\caminho\da\pasta\Esteira-de-demandas\backup_banco.ps1"
$acao = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
Register-ScheduledTask -TaskName "Esteira de Demandas - Backup do banco" -Action $acao `
  -Trigger (New-ScheduledTaskTrigger -Daily -At 18:00) -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable)
```

Restaurar um desses arquivos (**substitui os dados atuais do banco**):

```bash
docker cp backups/esteira_AAAA-MM-DD_HHMM.dump esteira-demandas-db-1:/tmp/restaurar.dump
docker exec esteira-demandas-db-1 pg_restore -U esteira -d esteira --clean --if-exists /tmp/restaurar.dump
```

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
| Gerenciar divisões, permissões e ver o uso do sistema | só o Administrador¹ | ❌ | ❌ |
| Comentar na demanda | ✅ | ✅ | ✅ (nas que vê) |
| Ver contagem de tempo por etapa | ✅ | ✅ | ❌ |

O perfil **Gestor do Plano** tem os mesmos poderes do Chefe de Divisão e, além disso, pode atribuir demandas **a si mesmo** (aceite automático). Como qualquer gestor, não pode aprovar a própria entrega.

¹ O **Administrador** é a conta do `ADMIN_EMAIL` do `.env` (não qualquer Gerente).

A tabela acima é o **padrão**. O Administrador pode ligar/desligar cada funcionalidade por perfil no menu **Permissões** (inclusive a quem cada perfil pode atribuir e se pode aprovar a própria entrega); "Restaurar padrão" desfaz tudo e cada alteração fica registrada. Aceitar, recusar e enviar para revisão continuam sempre com o atribuído, e só o Administrador acessa as telas de Permissões, Divisões e Uso do sistema.

O campo "Usuário atribuído" lista todos os usuários; os que o perfil logado não pode atribuir aparecem desabilitados, e a regra é **validada novamente no back-end** (`app/services/permissoes.py`).

### Fluxo da demanda
```
A atribuir → Aguardando aceite → Não iniciada → Em andamento → Em validação → Concluída

Aguardando aceite → Recusada (justificativa) → reatribuir → Aguardando aceite
Em validação → devolver (motivo) ou retomar → Em andamento
Qualquer status não final → cancelar (motivo) → Cancelada
```
- Gestor que atribui a demanda a si mesmo já fica "Não iniciada" (aceite automático).
- Recusada volta para quem atribuiu (aparece em **Minhas demandas › Recusadas**).
- A **Pasta da Rede** também pode ser alterada pelo responsável e pelos usuários de apoio, direto na tela da demanda.
- Demanda não finalizada com prazo vencido é destacada como **Atrasada**. O prazo é o **Prazo acordado** (definido pelo responsável na tela da demanda) ou, se ele estiver vazio, a data de término.
- No quadro, arrastar o card só é permitido para: aceitar, iniciar, enviar para revisão e aprovar, sempre uma etapa por vez. Ações que pedem texto (recusar, devolver, cancelar, atribuir) ficam na tela da demanda.

### Cadastro e acesso
- Qualquer pessoa pode criar a própria conta em **/cadastro** e já entra no sistema como **Usuário Comum**; o Gerente altera o perfil depois, em **Usuários**.
- Quem ainda não informou a divisão é levado à tela **Minha divisão** antes de usar o sistema (o Administrador está dispensado).

### Comentários e notificações
- Na tela da demanda, quem a vê pode comentar. O autor edita e remove o próprio comentário; um gestor também pode remover.
- O **sino** na barra superior avisa, nas demandas em que o usuário é responsável ou apoio, sobre comentários novos de outras pessoas (somem ao abrir a demanda) e sobre demandas em aberto cujo prazo vence nos próximos 3 dias (`DIAS_AVISO_PRAZO` em `app/services/demanda_service.py`).

### Contagem de tempo e indicadores
- O sistema calcula, a partir do histórico, quanto tempo a demanda passou em cada etapa (aguardando aceite, não iniciada, em andamento, em validação) e o tempo total até a conclusão. No quadro, o card sinaliza a demanda parada há 7 dias ou mais na mesma etapa (`app/services/tempos.py`).
- O menu **Indicadores** mostra entregas no prazo, taxa de devolução na validação, demandas concluídas e mediana do tempo até a conclusão, além de gráficos por etapa, eixo, status e carga por responsável. Filtros: período, responsável e divisão do responsável. Quem não vê todas as demandas vê os indicadores só das suas.
- Quadro e lista também filtram pela divisão do responsável.

### Uso do sistema (Administrador)
- A tela **Uso do sistema** (`/uso/`) mostra logins com sucesso, tentativas de login com erro (por e-mail e por IP), pessoas que usaram, acessos por dia, páginas mais acessadas e o último acesso de cada usuário.
- Cada tentativa de login e cada página aberta por usuário logado ficam gravadas nas tabelas `tentativas_login` e `acessos_pagina`. Recarregar a mesma página em até 30 minutos conta uma única visita (`INTERVALO_VISITA` em `app/services/uso_service.py`).

### Divisões
- Cadastradas pelo Administrador no menu **Divisões**. Cada divisão indica onde aparece: no **cadastro de usuários** (criação de conta, Usuários e "Minha divisão") e/ou nas **demandas** (criação e edição).
- Padrão: DIO, DPO e GGO em ambos; SR só para usuários; DIO/DPO, DPO/DIO e GGO/DPO/DIO só nas demandas.
- A sigla não pode ser alterada nem excluída, pois usuários e demandas a guardam como texto. Uma divisão **inativa** some das opções, mas quem já a usa continua com ela.

### Matriz GUT
- G, U e T: inteiros de 1 a 5. **P = G × U × T** (1 a 125), calculado pelo sistema.
- Faixas: **Baixa** 1–17 · **Média** 18–47 · **Alta** 48–125 (ajustáveis em `app/services/gut.py`).
- Sem os três pesos: "Aguardando priorização" (fica por último na ordenação).
- Toda alteração de pesos é registrada no histórico com valores antigos e novos.

---

## 6. Estrutura do projeto

```
app/
  __init__.py          # create_app (application factory)
  extensions.py        # db, migrate, login_manager, csrf
  cli.py               # comandos: flask seed, flask criar-usuario
  template_helpers.py  # filtros e variáveis globais dos templates (datas, notificações do sino)
  models/              # M — Usuario, Eixo, Divisao, Demanda, HistoricoDemanda, ComentarioDemanda,
                       #     LeituraComentarios, PermissaoPerfil, HistoricoPermissao, TentativaLogin, AcessoPagina
  seed_data/           # plano_de_trabalho.csv (carga inicial)
  services/            # regras de negócio
    permissoes.py      #   matriz de permissões (puro)
    fluxo.py           #   máquina de estados (puro)
    gut.py             #   cálculo e faixas GUT (puro)
    tempos.py          #   contagem de tempo por etapa, a partir do histórico
    demanda_service.py #   criação, atribuição, fluxo, comentários, consultas
    divisao_service.py #   cadastro de divisões e opções dos formulários
    permissao_service.py # permissões por perfil gravadas no banco
    carga_inicial.py   #   importação do plano de trabalho
    uso_service.py     #   registro de logins/páginas e tela de uso do sistema
    usuario_service.py, indicadores_service.py, exportacao_service.py
  controllers/         # C — blueprints: auth, demandas, usuarios, divisoes, indicadores, permissoes, uso
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
