"""Orquestador MALS — bucle cerrado state-driven de 9 agentes.

Encadena Head → Seniors → Especialistas según `status_flujo` hasta APROBADO
o hasta agotar el tope de ciclos (protección anti-loop infinito).
"""

from __future__ import annotations

from typing import Optional

from llm_provider import DEFAULT_CLAUDE_MODEL, LLMProvider
from mals.agents.head_of_legal import HeadOfLegal
from mals.agents.senior_a import SeniorA
from mals.agents.senior_b import SeniorB
from mals.agents.specialists.causas import AgenteCausas
from mals.agents.specialists.contratos import AgenteContratos
from mals.agents.specialists.riesgos import AgenteRiesgos
from mals.agents.specialists.sociedades import AgenteSociedades
from mals.agents.specialists.soporte_a import AgenteSoporteA
from mals.agents.specialists.soporte_b import AgenteSoporteB
from mals.state import LegalState


class MALSOrchestrator:
    """Motor del loop jerárquico MALS."""

    def __init__(
        self,
        *,
        provider: Optional[LLMProvider] = None,
        model: str = DEFAULT_CLAUDE_MODEL,
        max_ciclos: int = 10,
        verbose: bool = True,
    ) -> None:
        self.max_ciclos = max_ciclos
        self.verbose = verbose

        # Nivel 1–2
        self.head = HeadOfLegal(provider=provider, model=model)
        self.senior_a = SeniorA(provider=provider, model=model)
        self.senior_b = SeniorB(provider=provider, model=model)

        # Nivel 3
        self.causas = AgenteCausas(provider=provider, model=model)
        self.contratos = AgenteContratos(provider=provider, model=model)
        self.sociedades = AgenteSociedades(provider=provider, model=model)
        self.riesgos = AgenteRiesgos(provider=provider, model=model)
        self.soporte_a = AgenteSoporteA(provider=provider, model=model)
        self.soporte_b = AgenteSoporteB(provider=provider, model=model)

    def _log(self, msg: str) -> None:
        if self.verbose:
            print(msg)

    def _correr_track_a(self, state: LegalState) -> None:
        self._log(" -> Activando Ala de Litigios y Contratos (Senior A + Especialistas)")
        # Especialistas escriben sus reportes en el State (no avanzan status_flujo)
        self.causas.run(state)
        self.contratos.run(state)
        self.soporte_a.run(state)
        # Senior consolida y avanza a REVISION_HEAD o PROCESANDO_B
        self.senior_a.run(state)

    def _correr_track_b(self, state: LegalState) -> None:
        self._log(
            " -> Activando Ala Corporativa y Compliance (Senior B + Especialistas)"
        )
        self.sociedades.run(state)
        self.riesgos.run(state)
        self.soporte_b.run(state)
        self.senior_b.run(state)

    def ejecutar_sistema(self, consulta_usuario: str) -> LegalState:
        """Ejecuta el bucle hasta APROBADO (o tope de ciclos). Devuelve el State final."""
        state = LegalState(consulta_usuario=consulta_usuario, status_flujo="TRIAGE")
        ciclo = 1

        while state.status_flujo != "APROBADO" and ciclo <= self.max_ciclos:
            self._log(f"\n[CICLO {ciclo}] Ejecutando estado: {state.status_flujo}")
            status = state.status_flujo

            if status == "TRIAGE":
                # Head analiza y escribe tareas_senior_a / tareas_senior_b
                self.head.run(state)

            elif status in {"PROCESANDO_A", "PROCESANDO_AMBOS"}:
                self._correr_track_a(state)
                # Si el Head pidió ambos tracks, Senior A deja PROCESANDO_B
                # cuando B aún no reportó → lo resolvemos en el mismo ciclo.
                if state.status_flujo == "PROCESANDO_B":
                    self._log(
                        f"\n[CICLO {ciclo}] Continuación mismo ciclo: "
                        f"{state.status_flujo}"
                    )
                    self._correr_track_b(state)

            elif status == "PROCESANDO_B":
                self._correr_track_b(state)

            elif status == "REVISION_HEAD":
                self._log(
                    " -> El Head of Legal audita la calidad del trabajo consolidado..."
                )
                # Si calidad < 9 → historial_criticas + PROCESANDO_A/B/AMBOS (loop)
                self.head.run(state)

            else:
                raise RuntimeError(
                    f"Estado de flujo no reconocido en orquestador: '{status}'"
                )

            ciclo += 1

        if state.status_flujo != "APROBADO":
            self._log(
                f"\n[STOP] Tope de {self.max_ciclos} ciclos sin APROBADO. "
                f"Estado final: {state.status_flujo} · "
                f"calidad={state.evaluacion_calidad}"
            )
        else:
            self._log("\n[OK] Dictamen aprobado por Head of Legal.")

        return state

    def dictamen_final(self, consulta_usuario: str) -> str:
        """Atajo: corre el sistema y devuelve solo el dictamen ejecutivo."""
        state = self.ejecutar_sistema(consulta_usuario)
        return state.dictamen_ejecutivo_final
