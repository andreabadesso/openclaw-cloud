from dataclasses import dataclass, field


@dataclass
class NicheConfig:
    slug: str
    name: str
    icon: str
    recommended_providers: list[str] = field(default_factory=list)
    system_prompt: str = ""


NICHES: dict[str, NicheConfig] = {
    "pharmacy": NicheConfig(
        slug="pharmacy",
        name="Farmacia",
        icon="💊",
        recommended_providers=["google"],
        system_prompt=(
            "Voce e um assistente farmaceutico especializado. "
            "Seu papel e ajudar farmaceuticos e atendentes com consultas de bulas, "
            "interacoes medicamentosas, controle de estoque e validade, "
            "atendimento ao cliente e integracao com sistemas de gestao. "
            "Sempre responda em portugues brasileiro. "
            "Seja preciso com informacoes sobre medicamentos e alerte sobre "
            "interacoes perigosas ou contraindicacoes."
        ),
    ),
}
