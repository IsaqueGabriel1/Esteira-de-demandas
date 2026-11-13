@echo off
cd /d "C:\caminho\para\seu\projeto"
docker compose -f docker-compose.yml -f docker-compose.rede.yml up -d --build