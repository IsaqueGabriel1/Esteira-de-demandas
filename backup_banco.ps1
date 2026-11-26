# Backup diário do banco da Esteira de Demandas (agendado no Agendador de Tarefas do Windows).
# Gera um pg_dump no formato custom (já compactado) em backups\ e apaga os com mais de $DiasRetencao dias.
# Restauração: veja a seção "Backup e restauração do banco" do README.
param(
    [int]$DiasRetencao = 30,
    [string]$Container = "esteira-demandas-db-1"
)

$ErrorActionPreference = "Stop"
$pasta = Join-Path $PSScriptRoot "backups"
New-Item -ItemType Directory -Force $pasta | Out-Null
$log = Join-Path $pasta "backup.log"

function Escrever-Log($mensagem) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $mensagem" | Out-File -Append -Encoding utf8 $log
}

try {
    $arquivo = Join-Path $pasta ("esteira_{0}.dump" -f (Get-Date -Format "yyyy-MM-dd_HHmm"))

    # O dump é gerado dentro do container e copiado com docker cp (o pipe do PowerShell 5.1 corrompe binários)
    docker exec $Container sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/backup.dump'
    if ($LASTEXITCODE -ne 0) { throw "pg_dump falhou (o Docker Desktop está aberto?)" }
    docker cp "${Container}:/tmp/backup.dump" $arquivo
    if ($LASTEXITCODE -ne 0) { throw "docker cp falhou" }
    docker exec $Container rm -f /tmp/backup.dump | Out-Null

    $tamanho = (Get-Item $arquivo).Length
    if ($tamanho -lt 1024) { throw "arquivo gerado muito pequeno ($tamanho bytes): $arquivo" }
    Escrever-Log ("OK  {0} ({1:N0} KB)" -f (Split-Path $arquivo -Leaf), ($tamanho / 1KB))

    Get-ChildItem $pasta -Filter "esteira_*.dump" |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$DiasRetencao) } |
        ForEach-Object { Remove-Item $_.FullName -Force; Escrever-Log "Removido (mais de $DiasRetencao dias): $($_.Name)" }
}
catch {
    Escrever-Log "ERRO  $_"
    exit 1
}
