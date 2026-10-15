"""Generate manuscript figures only from frozen outputs and read-only audit data."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "paper_audit" / "outputs" / "nature_revision_audit.json"
FIGURES = ROOT / "paper_audit" / "figures"
ANCHOR = ROOT / "outputs" / "pilot_fi_anchor"
COFI = (
    ROOT / "cofi_rf_identifiability" / "stage0_real_rf" / "native_na_control"
    / "runs" / "paired_support_neutral_confirmatory_v1" / "joint_summary.json"
)


def save(fig: plt.Figure, name: str) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(FIGURES / f"{name}.png", dpi=210, bbox_inches="tight")
    plt.close(fig)


def anchor_and_cofi(audit: dict) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig = plt.figure(figsize=(7.3, 5.3), layout="constrained")
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.15])
    ax_time = fig.add_subplot(gs[0, :])
    ax_audit = fig.add_subplot(gs[1, 0])
    ax_cofi = fig.add_subplot(gs[1, 1])

    # A pre-existing illustrative trajectory: seed 1, quadratic alternative.
    seed = json.loads((ANCHOR / "seed_01.json").read_text(encoding="utf-8"))
    native = seed["arms"]["native"]["rounds"]
    neutral = seed["arms"]["neutral"]["rounds"]
    for y, rounds, colour, label in (
        (1.0, native, "#235789", "Native represented"),
        (0.5, neutral, "#569c75", "Neutral represented"),
    ):
        t_active = [r["t"] for r in rounds if r["quad"]["alive"]]
        t_absent = [r["t"] for r in rounds if not r["quad"]["alive"]]
        ax_time.scatter(t_active, np.full(len(t_active), y), s=25, c=colour, label=label)
        ax_time.scatter(t_absent, np.full(len(t_absent), y), s=16, c="#d1d5db")
    first_violation = next(r["t"] for r in native if r["quad"]["violated"])
    first_confirmed = next(r["t"] for r in native if r["quad"]["excluded"])
    ax_time.axvline(7, color="#235789", ls="--", lw=1.2)
    ax_time.axvline(first_violation, color="#d99032", ls="--", lw=1.2)
    ax_time.axvline(first_confirmed, color="#aa3a3a", ls=":", lw=1.5)
    ax_time.text(7.2, 1.23, "Native loss, g7", color="#235789", fontsize=8)
    ax_time.text(12.5, 0.13, "first chi-square\nviolation, g18", color="#a96817", fontsize=8)
    ax_time.text(19.2, 1.23, "confirmed exclusion, g19", color="#aa3a3a", fontsize=8)
    ax_time.set(xlim=(-0.5, 25.5), ylim=(0.0, 1.45), xlabel="Round", yticks=[0.5, 1.0])
    ax_time.set_yticklabels(["Neutral", "Native"])
    ax_time.set_title("a  An illustrative evidence-lag trajectory (seed 1, quadratic family)", loc="left", fontweight="bold")
    ax_time.spines[["top", "right", "left"]].set_visible(False)
    ax_time.tick_params(axis="y", length=0)

    # Post-hoc sensitivity stratification of the frozen 78 events.
    clean = audit["anchor"]["no_chi2_violation_at_elimination"]
    first = audit["anchor"]["first_chi2_violation_at_elimination"]
    ax_audit.bar([0, 1], [clean, first], color=["#569c75", "#d99032"], width=0.6)
    for x, n in enumerate((clean, first)):
        ax_audit.text(x, n + 1, str(n), ha="center", fontsize=9)
    ax_audit.set_xticks([0, 1], ["No violation\nat loss", "First violation\nat loss"])
    ax_audit.set(ylabel="Native loss events", ylim=(0, 60))
    ax_audit.set_title("b  Frozen events, stratified post hoc", loc="left", fontweight="bold")
    ax_audit.spines[["top", "right"]].set_visible(False)
    ax_audit.text(0.0, 0.97, "Neither group meets the frozen\ntwo-round exclusion rule at loss", transform=ax_audit.transAxes, va="top", fontsize=7.5)

    # Independent real-observation confirmatory result at registered matched fit.
    cofi = json.loads(COFI.read_text(encoding="utf-8"))
    ratios = np.asarray(cofi["primary_envelope"]["seed_ratios"], dtype=float)
    assert len(ratios) == 10
    ax_cofi.axhline(1.0, color="0.5", lw=1, ls="--")
    ax_cofi.scatter(range(1, 11), ratios, color="#235789", s=26, zorder=3)
    ax_cofi.set(xlabel="Paired seed (401-410)", ylabel="Native / control envelope width", xticks=range(1, 11), ylim=(0.3, 1.08))
    ax_cofi.set_title("c  CoFI, fit-matched support width", loc="left", fontweight="bold")
    ax_cofi.spines[["top", "right"]].set_visible(False)
    ax_cofi.text(0.03, 0.04, "Median ratio 0.899; 8/10 narrower", transform=ax_cofi.transAxes, fontsize=7.7)

    save(fig, "fig2_anchor_cofi")


def camels(audit: dict) -> None:
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    rows = audit["camels"]["rows"]
    fig, (ax_trace, ax_distance) = plt.subplots(
        1, 2, figsize=(7.3, 3.9), width_ratios=[1.45, 1.0], layout="constrained"
    )
    array = []
    labels = []
    for row in rows:
        for arm in ("native", "neutral"):
            array.append([int(v > 0) for v in row[f"{arm}_counts_within_radius_by_generation"]])
            arm_label = "Nat" if arm == "native" else "Neu"
            labels.append(f"{row['seed']}/{row['sim_idx']} {arm_label}")
    ax_trace.imshow(array, cmap=ListedColormap(["#f5d5af", "#235789"]), vmin=0, vmax=1, aspect="auto")
    ax_trace.set_xticks(range(7), [f"g{g}" for g in range(7)])
    ax_trace.set_yticks(range(8), labels)
    for k, row in enumerate(rows):
        loss = row["loss_generation"]
        ax_trace.add_patch(plt.Rectangle((loss - 0.5, 2 * k - 0.5), 1, 1, fill=False, edgecolor="#aa3a3a", lw=2))
    ax_trace.set_title("a  Matched CAMELS proposal coverage", loc="left", fontweight="bold")
    ax_trace.legend(handles=[Patch(color="#235789", label="covered"), Patch(color="#f5d5af", label="not covered")], loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False, fontsize=8)

    ratios = [row["native_min_distance_by_generation"][row["loss_generation"]] / row["radius"] for row in rows]
    labels = [f"{row['seed']}/{row['sim_idx']}" for row in rows]
    ax_distance.axhline(1.0, color="#aa3a3a", ls="--", lw=1.1, label="frozen radius")
    ax_distance.scatter(range(4), ratios, color="#235789", s=35, zorder=3)
    ax_distance.set_xticks(range(4), labels, rotation=38, ha="right")
    ax_distance.set(ylabel="Nearest proposal distance / frozen radius", ylim=(0.98, 1.13))
    ax_distance.set_title("b  Coverage-boundary proximity", loc="left", fontweight="bold")
    ax_distance.spines[["top", "right"]].set_visible(False)
    ax_distance.text(0.02, 0.97, "Old cohort: post-hoc boundary check;\nindependent redraw null in Methods", transform=ax_distance.transAxes, va="top", fontsize=7.5)
    save(fig, "fig3_camels_proposal_audit")


def main() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    anchor_and_cofi(audit)
    camels(audit)
    print(FIGURES / "fig2_anchor_cofi.pdf")
    print(FIGURES / "fig3_camels_proposal_audit.pdf")


if __name__ == "__main__":
    main()
