# Phase 2 Targeted Code Audit（v0.1 → confirmatory 前）

**范围**: `pilot_truth_loss/` 仅审实现是否偏离冻结设计；不重审科学设计。  
**结论**: Phase 1 **READY**；Phase 2 runner 已接线；正式 20-seed **待你审核后执行**。

---

## 1. F1 / F2 / F3 是否等于冻结定义

| 端点 | 设计 | 实现 (`metrics.py`) | 判定 |
|------|------|---------------------|------|
| **F1** | `t_elim(truth)` 存在；`t_excl` 为 None 或 `t_elim < t_excl`；淘汰时 evidence 仍兼容 | L46–48: `compat = not rounds[t_elim][hump]["excluded"]`；`unsupported = compat and (t_excl is None or t_elim < t_excl)` | **PASS** |
| **F2** | 最终 incumbent = **冻结 competitor**（pow） | L59–63: `f2 = (incumbent == COMPETITOR_FAMILY)` | **PASS（有意更严）** |
| **F3** | 仅 F1 seeds；Neutral 在 Native `t_elim` 时 truth 仍 alive 且最终 incumbent = truth | L69–80: `if not f1_row["f1"]: applicable=False`；L112–120 分母 = `F3_applicable_n` | **PASS** |

### F1 细节

- `compat_at_elim` 使用 **`excluded`**（非 `violated`），与 Anchor E1 `_native_event_row` 完全一致（`pilot_fi_anchor/metrics.py` L46–48）。
- 含义：PERSIST=2 下，首轮 violated 但未 excluded 仍算 evidence-compatible——与 Anchor FI 口径一致。

### F2 有意更严（非实现偷懒）

- 设计 §1：**「最终 stable 选择 competitor 而非 truth」** + 冻结 competitor = **pow**。
- 代码：`incumbent == "pow"`，**不是** `incumbent != "hump"`。
- 影响：最终为 affine/quad 的 seed **不计入 F2**，即使也是 wrong lock-in。
- **判定**：这是预注册的 scientific claim（锁定 pow 为 truth-loss 对手），**不是**代码方便；若需更宽定义须升版本重审。

### F3 分母

```python
f3_applicable = [r for r in f3_rows if r["applicable"]]  # 仅 f1=True
F3_rescue_frac = f3k / len(f3_applicable)
```

- 非 F1 seed 的 `f3` 为 `None`，**不进入分母**。 **PASS**

---

## 2. Native/Neutral 是否复用 Anchor（无复制漂移）

| 检查 | 结果 |
|------|------|
| `pilot_truth_loss` 是否含 `loop.py` / `Arm` 副本 | **否** |
| Phase 1 是否跑 recursive loop | **否**（仅 static/sequential evidence） |
| Phase 2 路径 | `confirmatory.py`: `from pilot_fi_anchor.loop import run_seed` |
| loop 副本 | **无** `pilot_truth_loss/loop.py` |
| theta 导出 | Anchor `run_seed` final 增加 `arm_theta`（记录导出 only，无动力学变更） |

**判定**：无 allocation/support/evidence 复制；Phase 2 直接调用 Anchor `run_seed`。

---

## 3. Truth=hump / Competitor=pow 是否冻结

| 检查 | 位置 | 判定 |
|------|------|------|
| `COMPETITOR_FAMILY = "pow"` | `config.py` L32 | 硬编码常量 |
| Phase 2 metrics 读 config | `metrics.py` L30, L63 | 不调用 `select_competitor_by_rule` |
| 重选仅在校准 | `pair_calibration.select_competitor_by_rule` 仅 `--calibrate` 调用 | **PASS** |
| CAL-G2 | `chosen == config.COMPETITOR_FAMILY` | 防 post-hoc 换 pair |

**风险**：若 Phase 2 误调用 `run_pair_calibration()` 并依其输出改 config → 流程违规；实现上 metrics/gates **未**如此做。

---

## 4. Held-out 19 点隔离

| 用途 | 文件 | 是否接触 held-out |
|------|------|-------------------|
| Pair selection / fitting | `pair_calibration._initial_obs`, `_extended_obs` | **否**（仅 X0 + neutral sweep） |
| Evidence calibration | 同上 + anchor sim | **否** |
| HO1 evaluation | `metrics.held_out_rmse` | **是（唯一）** |
| _disjoint 断言 | `verify_held_out_disjoint`, `test_config` | 校验用 |

**判定**：**PASS** — held-out 未进入 fitting / evidence / support / allocation / pair selection。

---

## 5. PASS-T1/T2/T3 绝对阈值

| 常量 | 值 | 动态？ |
|------|-----|--------|
| `PASS_T1_MIN` | 4 | 否 |
| `PASS_T2_MIN` | 2 | 否 |
| `PASS_T3_FRAC` | 0.60 | 否 |

`gates.evaluate_confirmatory` 只读取上述常量。**PASS**

---

## 6. RNG / CRN / 20 seeds

| 路径 | RNG |
|------|-----|
| Phase 1 calibration fit | `default_rng(0)` — 仅静态校准，与 loop 隔离 |
| Phase 2（设计） | Anchor `run_seed` → `world_rng(seed)`, `fit_rng(seed)`, `alloc_rng(seed,kind,t)` |
| Seeds | `CONFIRMATORY_SEEDS = SEEDS` = 1..20（anchor import） |

**判定**：import `pilot_fi_anchor.loop` **不会**共享 mutable pilot 状态；每 seed 独立 `World(seed)`。**PASS**（待 Phase 2 runner 接线后复验）。

---

## 7. HO1 fitted-theta（v0.1.1 修复）

| 检查 | 实现 |
|------|------|
| 禁止 theta0 fallback | `held_out_rmse(seed, incumbent, theta)` — 缺 theta → `MissingFinalThetaError` |
| 读取最终拟合 | `extract_incumbent_theta(rec, arm)` ← `final.arm_theta[incumbent]` |
| HO1 聚合 | `compute_truth_loss_endpoints` → `HO1_per_seed`, `held_out_rmse_ratio_median`（F2 seeds） |

Anchor 变更：`loop.run_seed` final 字典增加 `arm_theta` 快照（**不**改 allocation/evidence/support）。

---

## 8. 审计清单（Phase 2 跑前勾选）

- [ ] F1/F2/F3 单元测试与 Anchor E1 对照通过
- [ ] held-out disjoint 测试通过
- [x] confirmatory runner 只 import `run_seed`，无 loop 副本
- [x] CLI 不重新选 pair（`--seeds` 不调用 calibration selection）
- [x] HO1 必须 fitted theta，无 theta0 fallback
- [ ] 输出写入 `outputs/pilot_truth_loss/`（跑时验证）
- [x] 20 seeds = anchor `SEEDS`

**当前状态**：Phase 1 ✅ | Phase 2 接线 ✅ | **审核后可跑 confirmatory**
