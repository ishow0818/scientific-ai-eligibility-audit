"""Full Evidence Gate arm — eligibility = not excluded; no pilot_fi_anchor edits."""
from __future__ import annotations

from typing import Any

import numpy as np

from pilot_fi_anchor.config import M, N_CAND, SIGMA, THETA_W
from pilot_fi_anchor.fitting import residual_field
from pilot_fi_anchor.loop import Arm
from pilot_fi_anchor.mechanisms import ALL_FAMILIES, FAMILIES

from .config import (
    FAMILY_ORDER,
    STATUS_ABORT_EMPTY,
    STATUS_ABORT_ZERO_MASS,
    STATUS_DECISION_EMPTY,
    STATUS_OK,
)
from .eligibility import eligible_not_excluded, select_incumbent_by_w_all


class EvidenceGateAbort(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or code)


class EvidenceGateArm(Arm):
    """Native mechanics with evidence-gated eligibility for allocate + incumbent.

    Weight pruning is shadow-only (diagnostics). ``alive`` is kept True so that
    internal w_surv mirrors full-simplex masses; decision/allocation ignore it.
    """

    def __init__(self, seed: int, world: Any):
        super().__init__(seed, "native", world, rediscovery_mode="off")
        self.shadow_alive: dict[str, bool] = {h: True for h in ALL_FAMILIES}
        self.shadow_t_cross: dict[str, int | None] = {h: None for h in ALL_FAMILIES}
        self.abort_status: str | None = None
        self.eligibility_audit: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ helpers
    def eligible_list(self) -> list[str]:
        return eligible_not_excluded(self.excluded)

    def _shadow_weight_diagnostics(self) -> None:
        """Record weight-threshold crossings without mutating decision eligibility."""
        mx = max(self.S.values())
        raw = {h: float(np.exp(self.S[h] - mx)) for h in ALL_FAMILIES}
        shadow = [h for h in ALL_FAMILIES if self.shadow_alive[h]]
        if not shadow:
            return
        zs = sum(raw[h] for h in shadow)
        if zs <= 0:
            return
        w_shadow = {h: (raw[h] / zs if self.shadow_alive[h] else 0.0) for h in ALL_FAMILIES}
        for h in list(shadow):
            if w_shadow[h] < THETA_W:
                self.shadow_alive[h] = False
                if self.shadow_t_cross[h] is None:
                    self.shadow_t_cross[h] = self.round

    def _allocate_evidence_gated(
        self, rng: np.random.Generator, w_full: dict[str, float]
    ) -> list[tuple[str | None, int]]:
        E = self.eligible_list()
        if not E:
            raise EvidenceGateAbort(STATUS_ABORT_EMPTY, "eligible set empty at allocate")
        mass = float(sum(float(w_full[h]) for h in E))
        if mass <= 0.0:
            raise EvidenceGateAbort(
                STATUS_ABORT_ZERO_MASS, "nonpositive weight mass on eligible set"
            )

        unmeasured = [i for i in range(N_CAND) if i not in self.measured]
        xq = self.world.grid[unmeasured]
        ranked: dict[str, list[int]] = {}
        for h in E:
            mech = FAMILIES[h]
            xs = np.array([self.world.x(i) for (_, i, _) in self.streams[h]])
            ys = np.array([y for (_, _, y) in self.streams[h]])
            if len(xs) == 0:
                continue
            rhat = residual_field(mech, self.stream_theta[h], xs, ys, xq)
            u = np.exp(-((rhat / SIGMA) ** 2))
            ranked[h] = [unmeasured[j] for j in np.argsort(-u)]

        probs = np.array([float(w_full[h]) for h in E], dtype=float)
        probs = probs / probs.sum()

        sites: list[tuple[str | None, int]] = []
        taken: set[int] = set()
        for _ in range(M):
            placed = False
            for _try in range(50):
                h = E[int(rng.choice(len(E), p=probs))]
                for cand in ranked.get(h, []):
                    if cand not in self.measured and cand not in taken:
                        sites.append((h, cand))
                        taken.add(cand)
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                # HARD: no silent fallback to arbitrary scan
                raise EvidenceGateAbort(
                    STATUS_ABORT_EMPTY,
                    "could not place measurement without rescue fallback",
                )
        return sites

    def _incumbent(self) -> str | None:
        h, status, _ = select_incumbent_by_w_all(self.w_all, self.excluded)
        if status != STATUS_OK:
            return None
        return h

    def _record(self) -> None:
        row: dict[str, Any] = {
            "t": self.round,
            "arm": "full_evidence_gate",
            "n_arm": len(self.measured),
            "incumbent": self._incumbent(),
            "eligible": {h: (not self.excluded[h]) for h in FAMILY_ORDER},
        }
        for h in ALL_FAMILIES:
            row[h] = {
                "S": float(self.S[h]),
                "w_all": float(self.w_all[h]),
                "w_surv": float(self.w_surv[h]),
                "alive": bool(self.alive[h]),  # kept True; not decision eligibility
                "shadow_alive": bool(self.shadow_alive[h]),
                "shadow_t_cross": self.shadow_t_cross[h],
                "t_elim": self.t_elim[h],
                "t_reentry": self.t_reentry[h],
                "t_excl": self.t_excl[h],
                "excluded": bool(self.excluded[h]),
                "violated": bool(self.prev_violated[h]),
                "stream_n": len(self.streams[h]),
            }
        self.rows.append(row)
        self.eligibility_audit.append(
            {
                "t": self.round,
                "eligible": [h for h in FAMILY_ORDER if not self.excluded[h]],
                "excluded": {h: bool(self.excluded[h]) for h in FAMILY_ORDER},
            }
        )

    def step(
        self,
        t: int,
        rng: np.random.Generator | None = None,
        w_override: dict[str, float] | None = None,
        record: bool = True,
    ) -> None:
        assert t == self.round + 1
        if self.abort_status is not None:
            return
        self.round = t
        assert rng is not None
        w_full = w_override if w_override is not None else self.w_all
        try:
            sites = self._allocate_evidence_gated(rng, w_full)
        except EvidenceGateAbort as exc:
            self.abort_status = exc.code
            return

        self._ingest(t, sites)
        self._refit_streams()
        self._update_support()
        # Do NOT call weight-based _check_elimination (would mutate alive for Native path).
        # Keep alive all-True; shadow diagnostics only.
        self._shadow_weight_diagnostics()
        self._update_evidence()
        if record:
            self._record()

    def round0(self) -> None:
        sites = [(None, i) for i in self.world.initial_sites()]
        self._ingest(0, sites)
        self._refit_streams()
        self._update_support()
        # no weight elimination
        self._update_evidence()
        self._record()

    def final_pack(self) -> dict[str, Any]:
        incumbent = self._incumbent()
        if self.abort_status is not None:
            status = self.abort_status
            incumbent = None
        elif incumbent is None:
            status = STATUS_DECISION_EMPTY
        else:
            status = STATUS_OK
        E = self.eligible_list()
        return {
            "incumbent": incumbent,
            "eligible": {h: (h in E) for h in FAMILY_ORDER},
            "excluded": dict(self.excluded),
            "shadow_alive": dict(self.shadow_alive),
            "shadow_t_cross": dict(self.shadow_t_cross),
            "t_excl": dict(self.t_excl),
            "alive_kept_true": dict(self.alive),
            "arm_theta": {h: dict(self.arm_theta[h]) for h in ALL_FAMILIES},
            "incumbent_theta": (
                dict(self.arm_theta[incumbent]) if incumbent is not None else None
            ),
            "primary_status": status,
            "abort_status": self.abort_status,
            "n_measured": len(self.measured),
            "decision_rule": "argmax w_all among excluded=False",
        }
