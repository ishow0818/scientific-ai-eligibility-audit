"""The closed loop: one Arm class drives both arms (Native / Neutral).

Per round: allocate -> measure -> PUBLIC stream refit -> support ->
elimination -> evidence -> record.  The ONLY structural difference between
arms is ``_allocate_*`` (Native: support-weighted proposals; Neutral: fixed
sweep).  Acquired measurements enter every hypothesis stream; proposer
credit is provenance only and does not gate evidence accessibility.

Determinism: allocation RNGs are passed in per round by the caller and are
seeded via SeedSequence([MASTER_SALT, seed, kind, "alloc", t]); fitting is
warm-started and deterministic (first-fit starts draw from a per-arm seeded
RNG stored at construction).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .config import (
    GAMMA,
    M,
    MASTER_SALT,
    N_CAND,
    NEUTRAL_J0,
    NEUTRAL_SPAN,
    R,
    SIGMA,
    THETA_W,
)
from .evidence_calibration import evidence_crit
from .fitting import fit, loglik, residual_field
from .mechanisms import ALL_FAMILIES, FAMILIES
from .perturbation import perturbation_targets


class Arm:
    def __init__(
        self,
        seed: int,
        kind: str,
        world: Any,
        *,
        rediscovery_on: bool = False,
        rediscovery_mode: str | None = None,
    ):
        assert kind in ("native", "neutral")
        self.seed = seed
        self.kind = kind
        self.world = world
        if rediscovery_mode is None:
            rediscovery_mode = "v1_on" if rediscovery_on else "off"
        assert rediscovery_mode in ("off", "v1_on", "v2_on")
        self.rediscovery_mode = rediscovery_mode
        self.rediscovery_on = rediscovery_mode == "v1_on"
        self.round = 0

        self.measured: set[int] = set()
        self.streams: dict[str, list[tuple[int, int, float]]] = {
            h: [] for h in ALL_FAMILIES
        }
        self.site_rows: list[dict[str, Any]] = []

        # stream fits (algorithmic support) and arm-wide fits (evidence)
        self.stream_fit: dict[str, np.ndarray | None] = {h: None for h in ALL_FAMILIES}
        self.stream_theta: dict[str, dict[str, float]] = {h: {} for h in ALL_FAMILIES}
        self.arm_fit: dict[str, np.ndarray | None] = {h: None for h in ALL_FAMILIES}
        self.arm_theta: dict[str, dict[str, float]] = {h: {} for h in ALL_FAMILIES}

        self.S: dict[str, float] = {h: -np.inf for h in ALL_FAMILIES}
        self.w_all: dict[str, float] = {h: 0.0 for h in ALL_FAMILIES}
        self.w_surv: dict[str, float] = {h: 0.0 for h in ALL_FAMILIES}

        self.alive: dict[str, bool] = {h: True for h in ALL_FAMILIES}
        self.t_elim: dict[str, int | None] = {h: None for h in ALL_FAMILIES}
        self.t_reentry: dict[str, int | None] = {h: None for h in ALL_FAMILIES}
        self.excluded: dict[str, bool] = {h: False for h in ALL_FAMILIES}
        self.t_excl: dict[str, int | None] = {h: None for h in ALL_FAMILIES}
        self.prev_violated: dict[str, bool] = {h: False for h in ALL_FAMILIES}
        self.reentry_audit: list[dict[str, Any]] = []

        self.rows: list[dict[str, Any]] = []
        self.schedule_pos = 0

        from .rng import fit_rng

        self.fit_rng = fit_rng(seed)

    # ------------------------------------------------------------------ setup
    def round0(self) -> None:
        """Shared initial design, credited PUBLIC (both arms bit-identical)."""
        sites = [(None, i) for i in self.world.initial_sites()]
        self._ingest(0, sites)
        self._refit_streams()
        self._update_support()
        self._update_evidence()
        self._record()

    # ------------------------------------------------------------------- round
    def step(
        self,
        t: int,
        rng: np.random.Generator | None = None,
        w_override: dict[str, float] | None = None,
        record: bool = True,
    ) -> None:
        assert t == self.round + 1
        self.round = t
        if self.kind == "native":
            assert rng is not None, "native allocation needs a seeded RNG"
            w_full = w_override if w_override is not None else self.w_all
            sites = self._allocate_native(rng, w_full)
        else:
            sites = self._allocate_neutral()

        self._ingest(t, sites)
        self._refit_streams()
        self._update_support()
        if t >= 1:
            self._check_elimination()
        self._update_evidence()
        if record:
            self._record()

    # ------------------------------------------------------------ allocation
    def _allocate_native(
        self, rng: np.random.Generator, w_full: dict[str, float]
    ) -> list[tuple[str | None, int]]:
        """Support-weighted proposal sampling (EXPERIMENT_DESIGN.md 3.1).

        Each surviving hypothesis nominates its top-5 sites by
        u(x) = exp(-(rhat(x)/sigma)^2) over unmeasured candidates; M draws
        proportional to survivor-normalised support; the measured site is
        credited to its proposer.
        """
        alive = [h for h in ALL_FAMILIES if self.alive[h]]
        unmeasured = [i for i in range(N_CAND) if i not in self.measured]
        xq = self.world.grid[unmeasured]

        ranked: dict[str, list[int]] = {}
        for h in alive:
            mech = FAMILIES[h]
            xs = np.array([self.world.x(i) for (_, i, _) in self.streams[h]])
            ys = np.array([y for (_, _, y) in self.streams[h]])
            if len(xs) == 0:
                continue
            rhat = residual_field(mech, self.stream_theta[h], xs, ys, xq)
            u = np.exp(-((rhat / SIGMA) ** 2))
            ranked[h] = [unmeasured[j] for j in np.argsort(-u)]

        probs = np.array([w_full[h] for h in alive], dtype=float)
        probs = probs / probs.sum()

        sites: list[tuple[str | None, int]] = []
        taken: set[int] = set()
        for _ in range(M):
            placed = False
            for _ in range(50):
                h = alive[int(rng.choice(len(alive), p=probs))]
                for cand in ranked[h]:
                    if cand not in self.measured and cand not in taken:
                        sites.append((h, cand))
                        taken.add(cand)
                        placed = True
                        break
                if placed:
                    break
            if not placed:  # degenerate fallback; should not trigger
                for cand in unmeasured:
                    if cand not in self.measured and cand not in taken:
                        sites.append((alive[0], cand))
                        taken.add(cand)
                        placed = True
                        break
        return sites

    def _allocate_neutral(self) -> list[tuple[str | None, int]]:
        """Fixed support-independent sweep (EXPERIMENT_DESIGN.md 3.2)."""
        sites: list[tuple[str | None, int]] = []
        total = R * M
        for _ in range(M):
            j = self.schedule_pos
            if j >= total:
                break
            idx = NEUTRAL_J0 + (NEUTRAL_SPAN * j) // (total - 1)
            self.schedule_pos += 1
            sites.append((None, idx))  # None credit = PUBLIC
        return sites

    # -------------------------------------------------------------- ingestion
    def _ingest(self, t: int, sites: list[tuple[str | None, int]]) -> None:
        for h_credit, idx in sites:
            assert idx not in self.measured, "no revisits allowed"
            self.measured.add(idx)
            y = self.world.y(idx)
            # PUBLIC evidence: every acquired point updates all hypothesis streams.
            for h in ALL_FAMILIES:
                self.streams[h].append((t, idx, y))
            credit = h_credit if h_credit is not None else "PUBLIC"
            self.site_rows.append(
                {"t": t, "idx": idx, "x": self.world.x(idx), "y": y,
                 "credit": credit}
            )

    # ------------------------------------------------------------------ support
    def _refit_streams(self) -> None:
        for h in ALL_FAMILIES:
            mech = FAMILIES[h]
            xs = np.array([self.world.x(i) for (_, i, _) in self.streams[h]])
            ys = np.array([y for (_, _, y) in self.streams[h]])
            z = fit(mech, xs, ys, warm=self.stream_fit[h], rng=self.fit_rng)
            self.stream_fit[h] = z
            self.stream_theta[h] = mech.from_fit(z)

    def _update_support(self) -> None:
        t = self.round
        S: dict[str, float] = {}
        for h in ALL_FAMILIES:
            mech = FAMILIES[h]
            S[h] = float(
                sum(
                    GAMMA ** (t - ti)
                    * loglik(mech, self.stream_theta[h], self.world.x(i), y)
                    for (ti, i, y) in self.streams[h]
                )
            )
        self.S = S
        mx = max(S.values())
        raw = {h: np.exp(S[h] - mx) for h in ALL_FAMILIES}
        zsum = sum(raw.values())
        self.w_all = {h: raw[h] / zsum for h in ALL_FAMILIES}
        alive = [h for h in ALL_FAMILIES if self.alive[h]]
        zs = sum(raw[h] for h in alive)
        self.w_surv = {
            h: (raw[h] / zs if self.alive[h] else 0.0) for h in ALL_FAMILIES
        }

    def _hypothetical_w_surv(self, h: str) -> float:
        """Survivor-normalized weight if h were re-admitted to the alive set."""
        raw = {fam: np.exp(self.S[fam] - max(self.S.values())) for fam in ALL_FAMILIES}
        zs = sum(raw[fam] for fam in ALL_FAMILIES if self.alive[fam] or fam == h)
        return float(raw[h] / zs) if zs > 0 else 0.0

    def _any_elimination_recorded(self) -> bool:
        return any(self.t_elim[h] is not None for h in ALL_FAMILIES)

    def _refresh_w_surv(self) -> None:
        mx = max(self.S.values())
        raw = {h: np.exp(self.S[h] - mx) for h in ALL_FAMILIES}
        alive = [h for h in ALL_FAMILIES if self.alive[h]]
        zs = sum(raw[h] for h in alive)
        self.w_surv = {
            h: (raw[h] / zs if self.alive[h] else 0.0) for h in ALL_FAMILIES
        }

    def _reconstruct_alive_from_current_state(self) -> None:
        """CAMELS-aligned v2: full-pool eligibility from current w_all (no special gate)."""
        prev = dict(self.alive)
        for h in ALL_FAMILIES:
            eligible = self.w_all[h] >= THETA_W
            self.alive[h] = eligible
            if prev[h] and not eligible and self.t_elim[h] is None:
                self.t_elim[h] = self.round
            if not prev[h] and eligible:
                if self.t_reentry[h] is None:
                    self.t_reentry[h] = self.round
                self.reentry_audit.append(
                    {
                        "seed": self.seed,
                        "alternative_id": h,
                        "round": self.round,
                        "g_loss": self.t_elim[h],
                        "t_reentry": self.round,
                        "eligibility_quantity": float(self.w_all[h]),
                        "ordinary_threshold": float(THETA_W),
                        "criterion": "w_all >= THETA_W",
                        "participates_allocation_next_round": True,
                    }
                )

    def _check_elimination(self) -> None:
        if self.rediscovery_mode == "v2_on" and self._any_elimination_recorded():
            self._reconstruct_alive_from_current_state()
            self._refresh_w_surv()
            return

        for h in ALL_FAMILIES:
            if self.alive[h] and self.w_surv[h] < THETA_W:
                self.alive[h] = False
                if self.t_elim[h] is None:
                    self.t_elim[h] = self.round
        if self.rediscovery_on:
            for h in ALL_FAMILIES:
                if not self.alive[h] and self._hypothetical_w_surv(h) >= THETA_W:
                    self.alive[h] = True
                    if self.t_reentry[h] is None:
                        self.t_reentry[h] = self.round

    # ----------------------------------------------------------------- evidence
    def _update_evidence(self) -> None:
        """Frozen arm-wide chi2 criterion with sequential Bonferroni (§5)."""
        order = sorted(self.measured)
        xs = np.array([self.world.x(i) for i in order])
        ys = np.array([self.world.y(i) for i in order])
        n = len(xs)
        for h in ALL_FAMILIES:
            mech = FAMILIES[h]
            z = fit(mech, xs, ys, warm=self.arm_fit[h], rng=self.fit_rng)
            self.arm_fit[h] = z
            theta = mech.from_fit(z)
            self.arm_theta[h] = theta
            rss = float(np.sum((mech.predict(xs, theta) - ys) ** 2))
            stat = rss / (SIGMA * SIGMA)
            crit = evidence_crit(n, mech.p)
            violated = stat > crit
            excluded_now = bool(violated and self.prev_violated[h])
            if excluded_now and not self.excluded[h]:
                self.excluded[h] = True
                self.t_excl[h] = self.round
            self.prev_violated[h] = violated

    # ------------------------------------------------------------------- record
    def _incumbent(self) -> str | None:
        alive = [h for h in ALL_FAMILIES if self.alive[h]]
        if not alive:
            return None
        return max(alive, key=lambda h: self.w_surv[h])

    def _record(self) -> None:
        row: dict[str, Any] = {
            "t": self.round,
            "arm": self.kind,
            "n_arm": len(self.measured),
            "incumbent": self._incumbent(),
        }
        for h in ALL_FAMILIES:
            row[h] = {
                "S": float(self.S[h]),
                "w_all": float(self.w_all[h]),
                "w_surv": float(self.w_surv[h]),
                "alive": bool(self.alive[h]),
                "t_elim": self.t_elim[h],
                "t_reentry": self.t_reentry[h],
                "t_excl": self.t_excl[h],
                "excluded": bool(self.excluded[h]),
                "violated": bool(self.prev_violated[h]),
                "stream_n": len(self.streams[h]),
            }
        self.rows.append(row)


# --------------------------------------------------------------------- run one seed
def run_seed(
    seed: int,
    do_perturb: bool = True,
    rounds: int = R,
    *,
    rediscovery_on: bool = False,
    rediscovery_mode: str | None = None,
) -> dict[str, Any]:
    """Run both arms for one seed and return the full record dict.

    The perturbation branches are counterfactual one-round rollouts off the
    recorded state at each round t < R (see perturbation.py).
    """
    from .config import DELTA_PERTS
    from .rng import alloc_rng
    from .perturbation import run_perturb_pair
    from .world import World

    world = World(seed)
    if rediscovery_mode is None:
        rediscovery_mode = "v1_on" if rediscovery_on else "off"
    arms = {
        "native": Arm(seed, "native", world, rediscovery_mode=rediscovery_mode),
        "neutral": Arm(seed, "neutral", world, rediscovery_mode="off"),
    }
    for a in arms.values():
        a.round0()

    pert_records: list[dict[str, Any]] = []

    for t in range(1, rounds + 1):
        for kind, a in arms.items():
            a.step(t, rng=alloc_rng(seed, kind, t))

        if do_perturb and t < rounds:
            for kind, a in arms.items():
                for h in perturbation_targets(a):
                    for delta in DELTA_PERTS:
                        entry = run_perturb_pair(a, h, delta, seed, t)
                        pert_records.append(
                            {"t": entry["t"], "arm": entry["arm"], "h": entry["h"],
                             "delta": entry["delta"], "g": entry["g"],
                             "cos": entry["cos"]}
                        )

    return {
        "seed": seed,
        "arms": {
            kind: {
                "rounds": a.rows,
                "sites": a.site_rows,
                "final": {
                    "incumbent": a._incumbent(),
                    "alive": dict(a.alive),
                    "t_elim": dict(a.t_elim),
                    "t_reentry": dict(a.t_reentry),
                    "t_excl": dict(a.t_excl),
                    "excluded": dict(a.excluded),
                    "reentry_audit": list(a.reentry_audit),
                    "rediscovery_mode": a.rediscovery_mode,
                    # Final arm-wide fitted parameters (record export only).
                    "arm_theta": {h: dict(a.arm_theta[h]) for h in ALL_FAMILIES},
                },
            }
            for kind, a in arms.items()
        },
        "perturb": pert_records,
    }
