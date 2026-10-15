"""Observed / sealed-oracle store with a non-vacuous access log."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from pymatgen.core.composition import Composition


def precursor_key(precursors: list[str]) -> str:
    solid = [
        Composition(c).reduced_formula
        for c in precursors
        if c not in {"O2", "N2", "CO2", "H2O", "NH3", "NO"}
    ]
    return ", ".join(sorted(solid))


def temp_key(temp_c: int) -> str:
    return f"{int(temp_c)} C"


@dataclass
class AccessEvent:
    step: int
    caller: str
    route: str
    temperature_c: int
    phase: str
    allowed: bool
    hidden_candidate_high_t: bool
    already_revealed: bool
    present_in_algorithm_view: bool
    obtained_result: bool

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass
class VerifyStore:
    oracle_full: dict[str, Any]
    sealed_pairs: set[tuple[str, int]] = field(default_factory=set)
    observed: dict[str, Any] = field(default_factory=dict)
    revealed_pairs: set[tuple[str, int]] = field(default_factory=set)
    access_log: list[AccessEvent] = field(default_factory=list)
    _step: int = 0

    @classmethod
    def from_oracle(
        cls,
        oracle: dict[str, Any],
        sealed_pairs: set[tuple[str, int]] | None = None,
    ) -> VerifyStore:
        return cls(oracle_full=copy.deepcopy(oracle), sealed_pairs=set(sealed_pairs or ()))

    def algorithm_view(self) -> dict[str, Any] | None:
        if not self.observed:
            return None
        return copy.deepcopy(self.observed)

    def _record(
        self,
        *,
        caller: str,
        route: str,
        temperature_c: int,
        phase: str,
        allowed: bool,
        already_revealed: bool,
        present_in_algorithm_view: bool,
        obtained_result: bool,
    ) -> None:
        self._step += 1
        pair = (route, int(temperature_c))
        self.access_log.append(
            AccessEvent(
                step=self._step,
                caller=caller,
                route=route,
                temperature_c=int(temperature_c),
                phase=phase,
                allowed=allowed,
                hidden_candidate_high_t=pair in self.sealed_pairs,
                already_revealed=already_revealed,
                present_in_algorithm_view=present_in_algorithm_view,
                obtained_result=obtained_result,
            )
        )

    def _copy_node(self, route: str, temperature_c: int) -> dict[str, Any] | None:
        tk = temp_key(temperature_c)
        if route not in self.oracle_full:
            return None
        if tk not in self.oracle_full[route]["Temperatures"]:
            return None
        return copy.deepcopy(self.oracle_full[route]["Temperatures"][tk])

    def reveal(self, route: str, temperature_c: int, caller: str) -> dict[str, Any] | None:
        pair = (route, int(temperature_c))
        already = pair in self.revealed_pairs
        in_view = (
            route in self.observed
            and temp_key(temperature_c) in self.observed[route].get("Temperatures", {})
        )
        if pair in self.sealed_pairs:
            self._record(
                caller=caller,
                route=route,
                temperature_c=temperature_c,
                phase="decision",
                allowed=False,
                already_revealed=already,
                present_in_algorithm_view=in_view,
                obtained_result=False,
            )
            return None

        node = self._copy_node(route, temperature_c)
        obtained = node is not None
        if obtained:
            if route not in self.observed:
                self.observed[route] = {
                    "Precursor stoichiometry": self.oracle_full[route].get("Precursor stoichiometry"),
                    "Temperatures": {},
                }
            self.observed[route]["Temperatures"][temp_key(temperature_c)] = node
            self.revealed_pairs.add(pair)
        self._record(
            caller=caller,
            route=route,
            temperature_c=temperature_c,
            phase="decision" if pair not in self.sealed_pairs else "blocked",
            allowed=True,
            already_revealed=already,
            present_in_algorithm_view=in_view,
            obtained_result=obtained,
        )
        return node

    def peek_after_decision(self, route: str, temperature_c: int, caller: str) -> dict[str, Any] | None:
        """Open the sealed vault only after the gate decision."""
        pair = (route, int(temperature_c))
        node = self._copy_node(route, temperature_c)
        self._record(
            caller=caller,
            route=route,
            temperature_c=temperature_c,
            phase="post_decision",
            allowed=True,
            already_revealed=pair in self.revealed_pairs,
            present_in_algorithm_view=False,
            obtained_result=node is not None,
        )
        return node

    def log_skip(self, route: str, temperature_c: int, caller: str) -> None:
        pair = (route, int(temperature_c))
        self._record(
            caller=caller,
            route=route,
            temperature_c=temperature_c,
            phase="skipped_by_gate",
            allowed=False,
            already_revealed=pair in self.revealed_pairs,
            present_in_algorithm_view=False,
            obtained_result=False,
        )

    def log_probe(self, route: str, temperature_c: int, caller: str, in_view: bool, obtained: bool) -> None:
        pair = (route, int(temperature_c))
        self._record(
            caller=caller,
            route=route,
            temperature_c=temperature_c,
            phase="get_products_probe",
            allowed=in_view and pair not in self.sealed_pairs,
            already_revealed=pair in self.revealed_pairs,
            present_in_algorithm_view=in_view,
            obtained_result=obtained,
        )

    @property
    def decision_leakage_count(self) -> int:
        return sum(
            1
            for e in self.access_log
            if e.hidden_candidate_high_t and e.phase != "post_decision" and e.obtained_result
        )

    @property
    def decision_hidden_probes(self) -> int:
        return sum(
            1
            for e in self.access_log
            if e.hidden_candidate_high_t and e.phase != "post_decision"
        )
