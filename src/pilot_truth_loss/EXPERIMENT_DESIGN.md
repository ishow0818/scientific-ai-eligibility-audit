# Truth-Loss Failure Mode Extension — 实验设计 v0.1

**状态**: Phase 1（pair calibration）代码就绪；**Phase 2 confirmatory 未运行**。  
**依赖**: `pilot_fi_anchor` v1.1.2-b2-v2（只读 import；**不修改** Anchor confirmatory）。

---

## 1. 目标

在 Anchor FI 实验之外，独立检验 **truth-loss** 失败模式：

| 端点 | 含义 |
|------|------|
| **F1** | Native unsupported truth elimination：`t_elim(truth) < t_excl(truth)`（淘汰时 evidence 仍兼容） |
| **F2** | Native wrong lock-in：最终稳定选择 **competitor** 而非 truth |
| **F3** | Neutral truth rescue：F1 事件上，Neutral 保留并最终识别 truth |
| **HO1** | held-out grid 上 incumbent 相对真值的预测 RMSE（描述性；确认 wrong lock-in 的科学后果） |

Phase 2 **完全沿用** Anchor 的 allocation-only 干预、noise、budget、evidence、support、elimination；**仅** truth–competitor pair 与 held-out grid 为本 extension 冻结增量。

---

## 2. Phase 1 — Pair calibration（当前阶段）

**不跑** recursive Native/Neutral loop。

### 2.1 固定 DGP

- Truth family = **hump**（与 Anchor 相同，θ* = (8, 4.5, 2.5)）
- 初始观测 = Anchor `X0_IDX`（x ∈ [0.5, 2]）
- σ = 0.5，证据准则 = Anchor `ALPHA_EV` sequential Bonferroni + `PERSIST=2`

### 2.2 候选 competitor

`{affine, pow, expsat, quad}` — Anchor 四个假族。

### 2.3 预注册选择规则 PC1–PC6（**不得**用 failure rate）

| 规则 | 内容 |
|------|------|
| **PC1** | 所有 calibration seeds：truth 与 candidate 在**初始窗口**均 evidence-compatible |
| **PC2** | 初始 fitted-prediction gap ≤ 1σ（上界 sanity；排序用 median gap） |
| **PC3** | 全 Neutral 扫掠覆盖下，competitor 被 evidence 排除（PERSIST=2 静态代理） |
| **PC4** | 同上覆盖下，truth 仍 evidence-compatible |
| **PC5** | 全覆盖下 truth 总 log-likelihood > competitor（Neutral 可恢复 proxy） |
| **PC6** | x ≥ 5 尾区 competitor 与真值最大偏差 ≥ 1.5σ |

**选择**: 通过 PC1–PC6 的 candidate 中，取 **median initial gap 最小** 者；并列则 lexicographic family id。

### 2.4 冻结 pair（calibration 输出）

| 角色 | Family |
|------|--------|
| Truth | **hump** |
| Competitor | **pow** |

**依据**: median initial fitted-prediction gap = **0.083**（全 20 seeds），为四假族中最小；extended / sequential 安全门均通过。

---

## 3. Held-out grid

**不参与** fitting、allocation、elimination；仅 Phase 2 最终 RMSE 比较。

```
idx % 8 == 3,  120 <= idx <= 380,  不在 X0_IDX ∪ NeutralSweep
→ 19 点, x ≈ 3.1 … 9.5
```

---

## 4. Phase 2 — Confirmatory（设计冻结；未执行）

```bash
# 未来（v0.2+）；当前不运行
python -m pilot_fi_anchor --seeds 1..20   # 或专用 truth-loss runner 复用 loop
```

### 4.1 预注册 gates

**Calibration（Phase 1）**

| Gate | 条件 |
|------|------|
| CAL-G1 | PC 规则选出唯一 pair |
| CAL-G2 | 选出 == `config.COMPETITOR_FAMILY` |
| CAL-G3 | sequential truth excluded = 0 |
| CAL-G4 | extended competitor 排除 + truth 兼容（20/20） |
| CAL-G5 | extended separability |
| CAL-G6 | held-out 不相交且 n ≥ 10 |

**Confirmatory（Phase 2）**

| Gate | 阈值 |
|------|------|
| PASS-T1 (F1) | ≥ 4/20 seeds |
| PASS-T2 (F2) | ≥ 2/20 seeds |
| PASS-T3 (F3) | ≥ 60% of F1 seeds rescued by Neutral |
| DESC-HO1 | held-out RMSE ratio（描述性） |

---

## 5. 与 Anchor 关系

- **独立** sibling package `pilot_truth_loss/`
- **零修改** `pilot_fi_anchor/` confirmatory 产物
- 共享 mechanisms / world / evidence 常数（import only）
