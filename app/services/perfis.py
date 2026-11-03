"""Perfis de usuário do sistema."""


class Perfil:
    GERENTE = "GERENTE"
    CHEFE = "CHEFE"
    USUARIO = "USUARIO"

    TODOS = (GERENTE, CHEFE, USUARIO)
    GESTORES = frozenset({GERENTE, CHEFE})

    ROTULOS = {
        GERENTE: "Gerente",
        CHEFE: "Chefe de Divisão",
        USUARIO: "Usuário Comum",
    }

    @classmethod
    def rotulo(cls, perfil):
        return cls.ROTULOS.get(perfil, perfil)
