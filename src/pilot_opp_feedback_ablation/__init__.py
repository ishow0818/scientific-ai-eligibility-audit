"""Opportunity-Feedback Ablation for Anchor (allocation weights only).

Native arm: unchanged pilot_fi_anchor allocation (support-weighted proposer draws).
No-Opportunity-Feedback: same nomination / fit / prune / evidence; allocation
draws use uniform weights among currently alive candidates only.

Does not modify support-update or pruning weights; does not restore eliminated
candidates; does not cancel all recursive feedback.
"""

__version__ = "0.1.0"
