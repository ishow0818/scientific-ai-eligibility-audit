#!/usr/bin/env python3
"""Collect neighpy / ARROWS manifest provenance (read-only)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import site
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[1]
ROOT = AUDIT.parent
COFI = AUDIT / "provenance" / "cofi"
ARR = AUDIT / "provenance" / "arrows"
HIST = ARR / "historical_manifest"
COFI.mkdir(parents=True, exist_ok=True)
HIST.mkdir(parents=True, exist_ok=True)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def neighpy_report() -> dict:
    report: dict = {"status": "UNRESOLVED", "evidence": []}
    try:
        import neighpy  # type: ignore

        report["evidence"].append(f"import_ok version={getattr(neighpy, '__version__', '?')}")
        report["module_file"] = getattr(neighpy, "__file__", None)
        report["version"] = getattr(neighpy, "__version__", None)
    except Exception as e:  # noqa: BLE001
        report["evidence"].append(f"import_failed: {type(e).__name__}: {e}")

    # dist-info search
    candidates = []
    for base in list(site.getsitepackages()) + [site.getusersitepackages()]:
        b = Path(base)
        if not b.exists():
            continue
        candidates.extend(b.glob("neighpy*.dist-info"))
        candidates.extend(b.glob("neighpy*.egg-link"))
    report["dist_info_paths"] = []
    for di in candidates:
        entry = {"path": str(di).replace("C:\\Users\\", "C:\\Users\\<USER>\\")}
        for name in ("METADATA", "RECORD", "direct_url.json", "INSTALLER", "WHEEL"):
            f = di / name if di.is_dir() else None
            if f and f.exists():
                entry[name] = f.read_text(encoding="utf-8", errors="replace")[:4000]
        report["dist_info_paths"].append(entry)

    if report.get("version") and report["dist_info_paths"]:
        report["status"] = "CONFIRMED"
    elif report.get("version"):
        report["status"] = "STRONGLY_INFERRED"
    return report


def find_arrows_manifests() -> dict:
    # Locate frozen summary expected hash if present
    expected_hash = None
    expected_sources = []
    search_roots = [
        ROOT / "arrows_phase2e_gate_verification",
        ROOT / "arrows_phase2b_controlled_fi_replay",
        ROOT / "arrows_phase2c_strict_provenance",
        ROOT / "arrows_lowT_provenance_audit",
        ROOT / "outputs",
    ]
    frozen_summaries = []
    for r in search_roots:
        if not r.exists():
            continue
        frozen_summaries.extend(r.rglob("*summary*.json"))
        frozen_summaries.extend(r.rglob("*manifest*.csv"))
        frozen_summaries.extend(r.rglob("*manifest*.json"))

    # Extract sha256 mentions from phase2e outputs
    mentioned = set()
    for p in frozen_summaries:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for token in text.replace('"', " ").replace("'", " ").split():
            if len(token) == 64 and all(c in "0123456789abcdef" for c in token.lower()):
                mentioned.add(token.lower())
                expected_sources.append(str(p.relative_to(ROOT)))

    # Hash all candidate manifests
    found = []
    for r in search_roots:
        if not r.exists():
            continue
        for p in r.rglob("*manifest*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".csv", ".json", ".tsv", ".txt"}:
                continue
            try:
                dig = sha256(p)
            except Exception:
                continue
            found.append(
                {
                    "path": str(p.relative_to(ROOT)).replace("\\", "/"),
                    "sha256": dig,
                    "size": p.stat().st_size,
                }
            )

    matched = [f for f in found if f["sha256"] in mentioned]
    # Also search zip names mentioning manifest
    status = "CONFIRMED" if matched else ("PARTIAL_SEARCHED" if found else "UNRESOLVED")
    return {
        "status": status,
        "sha256_tokens_mentioned_in_summaries": sorted(mentioned)[:50],
        "mention_source_files_sample": sorted(set(expected_sources))[:40],
        "candidate_manifests": found[:200],
        "hash_matches_to_mentioned_tokens": matched,
        "n_candidates": len(found),
        "n_matches": len(matched),
    }


def main() -> None:
    n = neighpy_report()
    (COFI / "neighpy_raw.json").write_text(json.dumps(n, indent=2), encoding="utf-8")
    md = [
        "# NEIGHPY_PROVENANCE",
        "",
        f"Status: **{n['status']}**",
        "",
        f"- version: `{n.get('version')}`",
        f"- module_file: `{n.get('module_file')}`",
        "",
        "## Evidence",
    ]
    for e in n.get("evidence", []):
        md.append(f"- {e}")
    md.append("")
    md.append(f"dist-info entries found: {len(n.get('dist_info_paths', []))}")
    if n.get("dist_info_paths"):
        md.append("")
        md.append("### METADATA (truncated)")
        meta = n["dist_info_paths"][0].get("METADATA", "")
        md.append("```")
        md.append(meta[:2000])
        md.append("```")
        if "direct_url.json" in n["dist_info_paths"][0]:
            md.append("")
            md.append("### direct_url.json")
            md.append("```")
            md.append(n["dist_info_paths"][0]["direct_url.json"][:2000])
            md.append("```")
    (COFI / "NEIGHPY_PROVENANCE.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    a = find_arrows_manifests()
    (ARR / "arrows_manifest_search.json").write_text(
        json.dumps(a, indent=2), encoding="utf-8"
    )
    if a["hash_matches_to_mentioned_tokens"]:
        # copy matched files into historical_manifest
        for m in a["hash_matches_to_mentioned_tokens"]:
            src = ROOT / m["path"]
            dst = HIST / f"{m['sha256'][:12]}_{src.name}"
            dst.write_bytes(src.read_bytes())
        arr_md = [
            "# ARROWS_PROVENANCE_REPORT",
            "",
            "Status: **CONFIRMED** (at least one mentioned hash matched a local manifest file)",
            "",
            f"- mentioned sha256 tokens: {len(a['sha256_tokens_mentioned_in_summaries'])}",
            f"- matches: {a['n_matches']}",
            "",
            "## Matches",
        ]
        for m in a["hash_matches_to_mentioned_tokens"]:
            arr_md.append(f"- `{m['sha256']}` <- `{m['path']}`")
            arr_md.append(f"  copied under provenance/arrows/historical_manifest/")
    else:
        arr_md = [
            "# ARROWS_PROVENANCE_REPORT",
            "",
            "Status: **UNRESOLVED / PARTIAL** for exact historical byte-identical old manifest",
            "",
            f"- SHA-256 tokens mentioned in summaries: {len(a['sha256_tokens_mentioned_in_summaries'])}",
            f"- local manifest candidates hashed: {a['n_candidates']}",
            f"- exact hash matches to mentioned tokens: {a['n_matches']}",
            "",
            "See also `ARROWS_MANIFEST_EQUIVALENCE.md` if scientific fields can still be verified.",
            "",
            "Raw search: `arrows_manifest_search.json`",
        ]
        # equivalence stub filled later if needed
        eq = [
            "# ARROWS_MANIFEST_EQUIVALENCE",
            "",
            "Exact historical byte sequence referenced by frozen summary was **not recovered** on this machine search.",
            "",
            f"- mentioned tokens (sample): {a['sha256_tokens_mentioned_in_summaries'][:10]}",
            f"- current candidate count: {a['n_candidates']}",
            "",
            "Scientific five-case outputs should be verified separately from byte-identity of manifests.",
            "\"scientific outputs reproduce\" ≠ \"files byte-identical\".",
        ]
        (ARR / "ARROWS_MANIFEST_EQUIVALENCE.md").write_text(
            "\n".join(eq) + "\n", encoding="utf-8"
        )
    (ARR / "ARROWS_PROVENANCE_REPORT.md").write_text(
        "\n".join(arr_md) + "\n", encoding="utf-8"
    )
    print("neighpy:", n["status"], n.get("version"))
    print("arrows:", a["status"], "matches", a["n_matches"], "candidates", a["n_candidates"])


if __name__ == "__main__":
    main()
