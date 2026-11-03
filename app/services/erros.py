"""Exceções de regra de negócio. Os controllers as convertem em mensagens ao usuário."""


class RegraNegocioError(Exception):
    """Violação de uma regra de negócio (mensagem pronta para exibir ao usuário)."""

    def __init__(self, mensagem):
        super().__init__(mensagem)
        self.mensagem = mensagem


class PermissaoNegada(RegraNegocioError):
    """O usuário não tem permissão para realizar a ação."""


class TransicaoInvalida(RegraNegocioError):
    """A mudança de status pedida não é permitida a partir do status atual."""
