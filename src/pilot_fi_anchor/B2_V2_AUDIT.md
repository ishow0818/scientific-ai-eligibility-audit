# B2-v2 Targeted Audit Checklist

**版本**: pilot-v1.1.2-b2-v2  
**变更范围**: 仅证据判据 sequential Bonferroni；**不**改 E1/E2/E3、allocation、support/elimination、fitting。  
**v1.1.1 探索性 20-seed 结果**: KILL-B2 FAIL（neutral=1 seed 20，native=2 seeds 3/20）。  
**根因结论**: repeated testing（legacy α=0.01 未除以 R）；extreme-x hump 拟合**无** pathology。

**完成状态（v1.1.2）**: confirmatory 20-seed 输出已归档于
../outputs/pilot_fi_anchor/。所有 seed snapshots 标记 pilot-v1.1.2 且记录
alpha_ev=0.0004；该目录的 gates.json 报告 KILL-B1--B5 与 PASS-A1--A3
全部 PASS。本文件保留 B2-v2 修复范围、targeted-audit protocol 与旧批次的
失败来源，避免将 v1.1.1 与 v1.1.2 混为同一分析批次。

---

## 改前请先跑

```bash
pytest pilot_fi_anchor/tests -q
python -m pilot_fi_anchor --calibrate
```

---

## 5 项 targeted audit（改完后逐项勾选）

### 1. Sequential calibration 是否模拟正式 25-round 使用方式？

| 检查点 | 位置 | 预期 |
|--------|------|------|
| Neutral 快速代理 | `evidence_calibration.simulate_neutral_sequential` | round 0 + 25×5 Neutral 扫掠；`PERSIST=2`；warm-start fit；与 `loop.Arm._allocate_neutral` 同索引公式 |
| 正式 loop 校验 | `evidence_calibration.run_loop_b2_truth_check` | 调用 `run_seed(seed, do_perturb=False)` 完整 25 round、双臂 |
| 一致性测试 | `tests/test_b2_v2.py::test_sequential_sim_matches_neutral_loop` | seeds 1, 20：sim 与 neutral loop 的 hump `excluded` / `t_excl` 一致 |

**注意**: Native 采样路径与 Neutral 不同；B2 对 Native 的保障靠 `run_loop_b2_truth_check`，不能只靠 Neutral sequential sim。

---

### 2. B2-v2 是否与 calibration 完全一致？

| 检查点 | 位置 | 预期 |
|--------|------|------|
| 单一 α 来源 | `config.ALPHA_EV = 0.05 / (5 * R)` | 无其它 α 覆盖 |
| 单一 crit 函数 | `evidence_calibration.evidence_crit` | `loop.Arm._update_evidence` **必须**调用此函数（非内联 `chi2.ppf`） |
| CLI batch | `run_calibration_batch` → `--calibrate` | 输出含 `alpha_ev`、`sequential`、`loop_b2_check` |
| Gate 阈值 | `gates.py` KILL-B2 | `neutral=0, native<=1`（未改） |

---

### 3. 是否误改 E1/E2/E3、allocation、support/elimination？

**本 PR 允许改动的文件**:

- `config.py` — 仅 `ALPHA_EV` 注释/值（v1.1.2 已冻结）
- `evidence_calibration.py` — calibration + loop B2 check
- `loop.py` — **仅** `_update_evidence` 改用 `evidence_crit`（逻辑不变）
- `tests/test_b2_v2.py`, `tests/test_evidence.py`, `tests/test_evidence_calibration.py`
- 文档：`EXPERIMENT_DESIGN.md`, `README.md`, 本文件

**不得改动**（diff 应为空）:

- `metrics.py`（E1/E2/E3 端点定义）
- `gates.py`（阈值与 endpoint 键名）
- `loop.py` 中 `_allocate_*`, `_check_elimination`, `_update_support`
- `perturbation.py`, `rng.py`, `world.py`, `mechanisms.py`, `fitting.py`

---

### 4. 是否根据 seed 3/20 偷调参数？

| 检查点 | 预期 |
|--------|------|
| `config.py` 无 seed 字面量 | `tests/test_b2_v2.py::test_no_seed_specific_constants_in_config` |
| `B2_LOOP_CHECK_SEEDS = (3, 20)` | 仅用于 **验证** v1.1.1 失败案例，非调参 |
| `EXTREME_X_IDX` | 诊断用静态面板，不参与 loop 采样 |
| legacy α | `ALPHA_EV_LEGACY = 0.05/5` 仅对比报告，不参与正式 run |

---

### 5. Tests 是否真正覆盖新规则？

| 测试 | 覆盖 |
|------|------|
| `test_alpha_sequential_bonferroni` | α = 0.05/(5R) |
| `test_legacy_sequential_reproduces_v111_neutral_failure` | legacy 下 seed 20 neutral 误排除可复现 |
| `test_sequential_calibration_neutral_no_truth_exclusion` | current α 下 5-seed neutral 0 排除 |
| `test_extreme_x_no_fitting_pathology` | extreme-x 无 hump 崩溃 |
| `test_loop_uses_shared_evidence_crit` | loop 与 calibration 共用 crit |
| `test_v111_seed3_native_recovered_under_b2_v2` | seed 3（legacy native-only）双臂均不排除 |
| `test_v111_seed20_neutral_false_exclusion_fixed_native_may_stay_excluded` | seed 20 Neutral 误排除修复；Native 允许 ≤1 truth exclusion |
| `test_loop_b2_check_subset_passes` | `run_loop_b2_truth_check` 聚合 |
| `test_evidence_calibration_batch` | `--calibrate` 整条 pipeline |

---

## B2-v2 冻结决策

| 项 | 决定 |
|----|------|
| 机制 | **最小 sequential 修复**：`ALPHA_EV = 0.05 / (n_families × R)` |
| fitting | **不改**（σ=0 / 0.1 extreme-x sanity 通过） |
| χ² 阈值 | **不放宽**；只修正 repeated-testing 的 α |
| confirmatory | v1.1.2 20-seed output 已归档；结果见 ../outputs/pilot_fi_anchor/ |

---

## 关键 diff 摘要（供目视）

```python
# config.py (已有)
ALPHA_EV = 0.05 / (len(FAMILY_ORDER) * R)  # 0.0004

# loop.py _update_evidence (B2-v2)
crit = evidence_crit(n, mech.p)  # 替代 chi2.ppf(1.0 - ALPHA_EV, ...)
```

v1.1.1 → v1.1.2 预期 B2 变化（calibration + loop check seeds 3/20 已观测）:

| α | Neutral excluded | Native excluded (seeds 3/20) | B2 gate |
|---|------------------|------------------------------|---------|
| legacy 0.01 | seed 20 | seeds 3, 20 | FAIL |
| B2-v2 0.0004 | none | seed 20 only | **PASS** (native≤1) |

seed 20 native 在 B2-v2 下仍可能排除（t≈7）：属 Native 采样路径 + 随机噪声，**不是** fitting pathology；在预注册 B2 预算内，**不**需进一步放宽 χ² 或改 fitting。
