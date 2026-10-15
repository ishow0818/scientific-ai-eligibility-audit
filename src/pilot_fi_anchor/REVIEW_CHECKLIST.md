# 审查清单 — FI 锚点闭环实验 (pilot-v1.1)

**状态**: 设计 v1.1.2 / **B2-v2**（证据 sequential Bonferroni）。v1.1.1 是已被修复替代的探索性 20-seed 批次；v1.1.2 confirmatory 20-seed 已完成，结果记录在 ../outputs/pilot_fi_anchor/。

**结果状态**: seed_01.json--seed_20.json 均标记 pilot-v1.1.2、alpha_ev=0.0004；gates.json 报告 KILL-B1--B5 与 PASS-A1--A3 全部 PASS。B2_V2_AUDIT.md 保留修复范围与 targeted-audit protocol，不能被误读为仍待运行的 confirmatory 指令。

## 请先读

1. `EXPERIMENT_DESIGN.md` — 完整科学定义、冻结参数、PASS/KILL gates
2. `README.md` — 运行顺序与 kill 规则摘要
3. `config.py` — 单一参数事实来源（**禁止调参**）

## 审查重点（设计决策）

| # | 问题 | 当前选择 | 需您确认 |
|---|------|----------|----------|
| 1 | **唯一结构性不对称** | Native：support 加权选点；Neutral：固定扫掠 | allocation 机制差异 |
| 2 | **PUBLIC evidence** | 两臂：已获得 measurement 进入**全部** hypothesis stream | credit 仅 provenance |
| 3 | **初始观测匹配** | `NOISE_INIT_SEED=20260921` 生成 ε₀，**所有 seed/两臂共享** | 分叉点 bit-identical |
| 4 | **证据判据独立** | arm-wide χ²，α=0.05/(5·R)，2-round persistence | 与 support 零耦合；sequential Bonferroni |
| 5 | **淘汰 vs 排除** | algorithmic: w_surv < 0.02；evidential: 2-round χ² | t_elim / t_excl |
| 6 | **CRN 局部增益** | baseline/perturbed 分支共用 alloc RNG（fork_rng） | g 为 secondary |
| 7 | **focal victim** | 仅代表性案例 / 轨迹 | **不**决定 primary PASS |

## 机制族与 under-identification

- 真值：`hump` (A=8, μ=4.5, s=2.5)
- 假族：`affine / pow / expsat / quad` — 在 x∈[0.5,2] 上早期均 evidence-compatible
- 晚期 x≥5 区域预测分歧 → 假族终将被 evidence 排除（Neutral 应收敛 hump，KILL-B1）

## Primary endpoints（预注册）

| 端点 | 定义 |
|------|------|
| **E1** | seed-level：≥1 个 auditable false-family unsupported elimination（淘汰时仍 compatible） |
| **E2** | **ΔT_FI = t_excl^Native − t_elim^Native**（同一 Native 轨迹） |
| **E3** | causal rescue：Native 在 t 淘汰 h，Neutral 同时刻仍存活（与 E2 分开） |

Supporting：`ΔT_cross = t_excl^Neutral − t_elim^Native`（跨臂因果对比，非 primary temporal FI）

## Gates（结果出来后不得改阈值）

**KILL（任一失败 = pilot 无效）**: B1 Neutral≥18/20 收敛 hump；B2 真值误排除；B3 第0轮≥18/20 五族兼容；B4 匹配断言+Neutral g≡0；B5 ≤1 CPU 小时

**PASS（科学声称）**: A1 seed-level E1≥8/20；A2 rescue≥60%（unsupported 事件）；A3 frac(ΔT_FI≥1)≥60%（分母=全部 unsupported；截尾且 R>t_elim+1 计≥1）

**DESC-A4**: Native 最终 truth recovery — 仅描述性，**非** PASS gate

A1 在 3–7/20 → **AMBIGUOUS**，升 v2 重审，禁止静默调参。

## 代码结构

```
pilot_fi_anchor/
  EXPERIMENT_DESIGN.md   设计冻结稿 v1.1
  REVIEW_CHECKLIST.md    本文件
  config.py              冻结参数
  mechanisms.py          5 机制族 + 拟合空间
  world.py               噪声场 + 共享初始观测
  fitting.py             least_squares + 残差场
  loop.py                Native/Neutral 闭环（唯一差异：allocation）
  perturbation.py        CRN 局部扰动 + 实证增益 g（secondary）
  evidence_calibration.py  证据判据 sanity check
  rng.py                 SeedSequence + fork_rng (CRN)
  recorder.py / metrics.py / gates.py / analysis.py
  __main__.py            CLI
  tests/                 单元测试（不跑 pilot）
```

## 评审通过后运行顺序

```bash
pytest pilot_fi_anchor/tests -q
python -m pilot_fi_anchor --calibrate                 # 证据判据 sanity check
python -m pilot_fi_anchor --dry                      # 1 seed × 4 轮，不写文件
python -m pilot_fi_anchor --seeds 1..20              # 正式 pilot → outputs/pilot_fi_anchor/
python -m pilot_fi_anchor --seeds 1..20 --no-perturb # 可选加速
```

输出：`seed_*.json`, `endpoints.json`, `gates.json`, `summary_*.csv`

## 已知开放项（不在 v1 调参）

- γ、θ_w 灵敏度 → Phase 2 只报告、不作 gate
- Native 可能淘汰真值 hump → 如实报告（次级端点）
- 幂律在 x→0 奇异 → E2 截尾处理已预注册
- δ ∈ {0.01, 0.025, 0.05} 增益稳定性 → 正式运行前可再冻结主报告 δ
