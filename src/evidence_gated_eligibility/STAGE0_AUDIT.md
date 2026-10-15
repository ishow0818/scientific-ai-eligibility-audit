# Evidence-Gated Eligibility — Stage 0 代码审计

**日期：** 2026-10-12  
**范围：** 只读 `pilot_fi_anchor`（loop / fitting / world / rng / evidence / config）；不改算法、阈值、论文；不跑 smoke/正式实验。

## 1. 核心调用链（Native `Arm.step`，t≥1）

```
allocate(_allocate_native)
  → 读 self.alive（提名集合 / proposer 支撑）
  → 读 w_full（默认 self.w_all；可由 w_override 覆盖）
  → 不读 excluded
→ ingest（PUBLIC：新点进入全部 stream）
→ refit_streams（fit_rng；与 alive/excluded 无关）
→ update_support（算 S, w_all；w_surv 在 alive 上归一化）
→ check_elimination（w_surv < Θ_W → alive=False；不读 excluded）
→ update_evidence（χ² → violated/excluded；不改 alive）
→ record / incumbent = argmax_{alive} w_surv
```

Round 0：共享初始设计 → 同上（无 allocate / 无 elimination）。

## 2. 状态变量依赖矩阵

| 下游环节 | `alive` | `excluded` | `w_all` | `w_surv` |
|---|---|---|---|---|
| 提名集合 `_allocate_native` | **决定** | 否 | 否 | 否 |
| proposer 概率 | 支撑集=alive | 否 | **默认权重**（可 override） | 否 |
| stream 拟合 / PUBLIC 摄入 | 否 | 否 | 否 | 否 |
| 支持 `S`→`w_all` | 否 | 否 | 输出 | — |
| `w_surv` 定义 | **归一化支撑** | 否 | 输入 raw | 输出 |
| 权重剪枝 | 读/写 | 否 | 否 | **阈值比较** |
| χ² 证据审计 | 否（全族） | 写（粘性） | 否 | 否 |
| 最终 `incumbent` | **资格集** | 否 | 否 | **排序键** |

**关键事实：** 原生决策资格 = `alive`（由权重剪枝写入）；`excluded` 仅作后台证据标签，**不**门控选点或首位模型。

## 3. 与机会反馈消融的对比

| | Opp-Feedback Ablation | 本干预（Evidence Gate） |
|---|---|---|
| 隔离钩子 | `w_override` → proposer 概率 | 替换 **eligibility 集合**（allocate + incumbent） |
| 剪枝 | 保留 | A 保留；C **不**用剪枝作资格；B 离线改终局资格 |
| 证据 | 不变 | A/B 轨迹同 A；C 用 `excluded` 作资格 |
| 包位置 | `pilot_opp_feedback_ablation/` | `evidence_gated_eligibility/`（拟） |
| `pilot_fi_anchor` | 未改 | **不得改** |

`w_override` **不足**以实现 C：它不改变 `alive` 支撑集。C 必须在外部子类/包装中覆盖 allocate 的资格集与 `incumbent`，并停止把权重剪枝写入决策资格。

## 4. 机制隔离可行性

### Arm A — Native
- 直接调用现有 `Arm(..., kind="native")` + `alloc_rng(seed, "native", t)`。
- 复现目标：与 `run_seed(..., do_perturb=False)` Native 轨迹 bit 一致。

### Arm B — Decision-Only Gate（离线）
- **输入：** 完整 A 的 rounds/sites/`arm_theta`/`excluded`/`w_all`。
- **不**重跑闭环；不改历史选点。
- **终局决策：** 资格集 `E = {h: excluded[h]=False}`；首位 = `argmax_{h∈E} w_all[h]`。  
  （与原生「在资格集上对支持权重取 max」同构：在 `E` 上对 `w_all` 再归一化不改变 argmax。**不能**用原生终局 `w_surv`，因权重已剪枝者 `w_surv=0`。）
- 若 `E=∅`：记 **DECISION_EMPTY**（失败结局），禁止回退到权重剪枝集或 ground truth。

### Arm C — Full Evidence Gate（闭环）
- 外部 `EvidenceGateArm`（拟）继承/组合 `Arm`，**不修改** `pilot_fi_anchor` 源文件。
- 覆盖点（最小）：
  1. 分配资格 = `not excluded`（上一轮证据结束后的粘性标志）；
  2. proposer 权重 = 原 `w_all`，在资格集上归一化（无 floor、无探索奖励）；
  3. 终局 incumbent = `argmax` 同 B 规则；
  4. **不**将 `w_surv < Θ_W` 写入决策资格；权重跨越仅作 **shadow 诊断日志**（`t_weight_cross`），用于 FI 标签对比，不回流控制。
- 拟合 / PUBLIC / χ² 公式 / Θ_W 数值 / 预算：不变。

## 5. 边界与硬停止（禁止静默救援）

| 边界 | 原生行为 | 本设计 |
|---|---|---|
| 资格集空 | 权重剪枝下，单存活者 `w_surv=1`，**不会**全灭 | C/B：χ² 可排除全部 → **HARD_ABORT / DECISION_EMPTY**，禁止 fallback 选点或“复活” |
| `sum(w_all on eligible)≤0` | 不应出现（有限数据 raw>0） | 若出现 → **HARD_ABORT**，禁止 ε 平滑 |
| `excluded` 粘性 | 一旦排除不可逆 | **保持不可逆**；不增加 rediscovery |
| 后台证据 vs 在线资格 | 证据不改 alive | C：资格只读 `excluded`；shadow 权重事件不得叫作“排除” |
| allocate 退化 fallback（`alive[0]` 扫未测点） | 原码存在 | C **不得**在空资格时落入该路径；空集直接中止该臂 |

若实现时发现必须加救援才能跑通 → 本 Stage 要求 **先报告并停止**，不得偷加。

## 6. 潜在因果混淆

1. **C 改变数据轨迹**：资格门控改变选点 → 观测/支持/证据路径分叉；与 A 的终点差异是「资格政策的闭环效应」，不是纯标签重贴。B 用于分离「仅终局资格」效应。
2. **χ² 为 OPERATIONAL_ONLY**：误排除真实模型计入失败；不得当统计 oracle。
3. **RNG**：A/C 必须 CRN 同构（同 SeedSequence 构造、独立 Generator），否则资格效应与随机流混淆（参见 opp-ablation v0.1 教训）。
4. **评估网格若占用可测下标**：会改变 A 相对正式 Native 的行为 → **禁止**；评估点必须在候选网格外。
5. **把“保留更多候选”当成功**：明确禁止；Primary 是独立网格无噪声 RMSE。

## 7. Stage 0 结论（机制）

- 三臂可在 **不修改** `pilot_fi_anchor` 的前提下干净实现（A 直调；B 离线；C 外包资格策略）。
- 最大风险：C 空资格集与 χ² 操作性误排除；均以失败计数处理，不加救援。
- 详见 `POLICY_SPEC.md` / `EVALUATION_PROTOCOL.md` / `IMPLEMENTATION_PLAN.md`。
