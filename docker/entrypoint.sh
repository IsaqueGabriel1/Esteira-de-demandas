#!/bin/sh
# Inicialização do container da aplicação:
# 1) aplica as migrações do banco; 2) roda a carga inicial; 3) inicia o servidor.
set -e

echo ">> Aplicando migrações do banco..."
flask db upgrade

echo ">> Carga inicial (eixos e Gerente administrador)..."
flask seed

echo ">> Iniciando: $*"
exec "$@"
