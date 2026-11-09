"""Perfis de usuário do sistema."""


class Perfil:
    GERENTE = "GERENTE"
    CHEFE = "CHEFE"
    GESTOR_PLANO = "GESTOR_PLANO"
    USUARIO = "USUARIO"

    TODOS = (GERENTE, CHEFE, GESTOR_PLANO, USUARIO)
    GESTORES = frozenset({GERENTE, CHEFE, GESTOR_PLANO})
    # Perfis com os poderes do Chefe de Divisão (gestão restrita, sem os poderes do Gerente).
    GESTORES_RESTRITOS = frozenset({CHEFE, GESTOR_PLANO})

    ROTULOS = {
        GERENTE: "Gerente",
        CHEFE: "Chefe de Divisão",
        GESTOR_PLANO: "Gestor do Plano",
        USUARIO: "Usuário Comum",
    }

    @classmethod
    def rotulo(cls, perfil):
        return cls.ROTULOS.get(perfil, perfil)
