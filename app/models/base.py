from datetime import datetime, timezone


def agora():
    """Data/hora atual em UTC (sem timezone, para compatibilidade entre bancos)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
