# IMPLEMENTATION_PLAN — 最小改动与测试（Stage 0 → Stage 1）

**本 Stage 只设计，不实现、不跑 smoke/正式。**

## 1. 包布局（拟）

```
evidence_gated_eligibility/
  STAGE0_AUDIT.md          # 本阶段已写
  POLICY_SPEC.md
  EVALUATION_PROTOCOL.md
  IMPLEMENTATION_PLAN.md
  verdict.json
  __init__.py
  config.py                # EVAL grid, seeds 201–240, arm tags, abort codes
  eligibility.py           # eligible sets; decision_only_incumbent(w_all, excluded)
  eval_grid.py             # EVAL_X_MIDPOINTS; noiseless RMSE; RMSE_FAIL
  loop_ege.py              # run_paired_seed A+C; B from A log
  arm_evidence_gate.py     # EvidenceGateArm subclass/wrapper
  run_smoke.py             # Stage 1 only
  run_formal.py            # Stage 2 only；seeds 201–240
  tests/
    test_eligibility_policy.py
    test_eval_grid_disjoint.py
    test_native_reproduction.py
    test_decision_only_offline.py
    test_empty_eligible_aborts.py
```

**禁止修改：** `pilot_fi_anchor/**`、正式日志、论文 TeX、Θ_W、χ²、原生评分公式定义。

## 2. 最小代码触点

| 组件 | 做法 |
|---|---|
| A | `Arm(seed,"native",world,rediscovery_mode="off")` + 正式 `alloc_rng` 同构 CRN |
| B | 纯函数：读 A `final.excluded` + `final` 时 `w_all`（来自最后一轮 row）+ `arm_theta` → `incumbent_B` |
| C | `EvidenceGateArm`：覆盖 `step` / allocate 资格 / `_incumbent`；shadow 权重日志；空集 HARD_ABORT |
| 评估 | `eval_grid.py`；真值仅此处引用 `TRUTH` |
| RNG | 包内 `alloc_rng(seed,t)` = `SeedSequence([MASTER_SALT,seed,0,RNG_ALLOC,t])`；A/C 各 `default_rng` 一次 |

### C 覆盖伪码（示意）

```
step(t, rng):
  E = [h for h in families if not excluded[h]]
  if E empty: raise/return ABORT_EMPTY_ELIGIBLE
  sites = allocate_native_on(E, w_all, rng)  # 无 ε、无均匀回退
  ingest → refit → support
  shadow_weight_diagnostics()               # 不改 excluded/eligible
  update_evidence()                         # 原 χ²
  # eligible next round implied by excluded
  record()
```

不调用会把 `alive←False` 并影响分配的原生 `_check_elimination`（或调用后立即恢复决策资格与 `excluded` 对齐，且 **shadow** 另存）。推荐：**不调用**原生剪枝写 `alive`，保持 `alive≡True` 仅作内部兼容，决策只读 `excluded`。

## 3. 测试与通过条件（Stage 1 才跑）

| 测试 | 通过条件 |
|---|---|
| `test_eval_grid_disjoint` | 任一 `EVAL_X` 都不能等于 `linspace(0,10,401)` 中的点（容差 1e-15） |
| `test_decision_only_offline` | B 不新增 sites；`incumbent_B` 仅依赖 `excluded`+`w_all`；空 `excluded` 全 False 时若与 A 资格不同则结果可异 |
| `test_empty_eligible_aborts` | 人为全 `excluded=True` 时 C allocate / B 决策返回 ABORT/EMPTY，**无** fallback 选点 |
| `test_native_reproduction` | A 与 `run_seed(seed,do_perturb=False)` 的 Native `sites`+`t_elim`+`t_excl` 一致（seeds∈{1,3,20}） |
| `test_no_pilot_fi_anchor_diff` | git/文件哈希：实现阶段前后 `pilot_fi_anchor` 无改动 |
| Smoke（201–203） | 三臂跑完；写出 RMSE；无静默救援；A 复现通过 |

## 4. Stage 门禁

| Stage | 允许 | 禁止 |
|---|---|---|
| **0（本阶段）** | 文档 + verdict | 实现可选草稿；**禁止** smoke/正式 |
| 1 | 实现 + 单元测试 + smoke 201–203 | 正式 201–240；改阈值；改论文 |
| 2 | 正式 201–240 | 调参；按结果改网格 |

## 5. 实现风险清单（进入 Stage 1 前已关闭）

- [x] B 使用 `w_all` 而非 `w_surv`（已写入 POLICY）  
- [x] C 空资格 HARD_ABORT（已写入 POLICY）  
- [x] 评估点离网格（已写入 EVALUATION）  
- [x] CRN 与 opp-ablation v0.2 对齐（已写入 EVALUATION）  
- [x] χ² OPERATIONAL_ONLY + 真模型误排除计失败（已写入）  
- [x] 不修改 `pilot_fi_anchor`（已写入）  
