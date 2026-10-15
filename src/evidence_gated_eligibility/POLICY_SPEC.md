# POLICY_SPEC — A / B / C 三臂精确定义

版本：`ege-stage0-0.1.0`（设计冻结草案；实现前以本文件为准）  
χ² 状态：**OPERATIONAL_ONLY**（非严格校准统计相容 oracle）

## 共用不变项

| 项 | 冻结值 / 规则 |
|---|---|
| World / 噪声 / 初始设计 | `World(seed)`；`X0_IDX`；`SIGMA=0.5` |
| 预算 | `R=25`，`M=5` |
| 拟合 | 原 `fit` / warm-start / `fit_rng(seed)` |
| 支持 | `GAMMA=0.85` → `S` → `w_all`（全族 softmax） |
| 提名效用 | `u(x)=exp(-(r̂/σ)²)`，仅资格集内提名 |
| Θ_W | `0.02`（**不改数值**；C 不将其用作决策资格） |
| χ² | `stat=RSS/σ²`，`crit=χ²_{1-α,n-p}`，`α=0.05/(5R)`，连续 2 轮 → `excluded` 粘性 |
| 评分公式 | 在**当前资格集**上对支持权重取最大者（见下） |
| Ground truth | **仅**用于最终评价，不进入任何臂的决策 |

---

## Arm A — Native（原始基线）

**资格（决策 / 分配）：** `eligible_A(h) ⇔ alive[h]`  
**alive 更新：** `w_surv < Θ_W` → `alive←False`（不可逆；`rediscovery_mode=off`）  
**分配：** `_allocate_native(rng, w_full=w_all)`，支撑=`alive`  
**终局首位：** `incumbent = argmax_{h: alive[h]} w_surv[h]`  
**证据：** 原 `_update_evidence`（不门控资格）

语义：与现网 Anchor Native 完全一致。

---

## Arm B — Decision-Only Gate（离线终局干预）

**数据：** 与同一 seed 的 Arm A **逐点相同**的 `measured`、拟合、`w_all`、`excluded`、`arm_theta`。  
**不**重跑 allocate / ingest；**不**改变历史机会。

**终局资格：** `eligible_B(h) ⇔ (excluded[h] = False)`  
**终局首位：**

```
if eligible_B = ∅:
    incumbent_B = None   # 结局码 DECISION_EMPTY（失败）
else:
    incumbent_B = argmax_{h in eligible_B} w_all[h]
```

**说明：** 使用 A 终局的 `w_all`（全单纯形），**禁止**使用 A 的 `w_surv`（已剪枝者被置 0）。  
**禁止：** 用 holdout RMSE、真模型身份或任何评估误差在 B 内选模型。

**FI 标签：** 不重新定义；可报告「若沿用 A 的 t_elim 与 excluded，操作性 FI 是否成立」作描述，但不作为 B 的优化目标。

---

## Arm C — Full Evidence Gate（闭环干预）

**决策/分配资格：** `eligible_C(h) ⇔ (excluded[h] = False)`  
- Round t 的 allocate 使用 **t−1 结束时**的 `excluded`（round 0 后初始全为 False → 全员资格）。  
- `excluded` **粘性不可逆**（与原证据规则一致）。

**权重剪枝：** **不**写入 `eligible_C`。  
允许（且要求）写 **shadow 诊断**：

- `shadow_weight_cross[h]`：若按原生规则在当前 `w_surv_shadow` 上会触发剪枝，记录首次轮次；  
- 不改变 allocate / incumbent。

**分配：**

1. `E = {h: not excluded[h]}`  
2. 若 `E=∅` → **HARD_ABORT** 该 seed 的 C 臂（记录 `ABORT_EMPTY_ELIGIBLE`）；**禁止**调用原码“退化为 alive[0] 扫点”。  
3. 仅对 `h∈E` 做提名排序（原 `u(x)`）。  
4. `probs(h) ∝ w_all[h]`（h∈E），标准归一化；若 `sum(w_all[E])≤0` → **HARD_ABORT**（禁止 ε floor / 均匀回退）。  
5. 抽 M 个点；credit 规则同 Native。

**支持更新 / 拟合 / χ² / 预算：** 同 Native。  
**终局首位：** 同 B 规则（`argmax` on `w_all` over `not excluded`）；空集 → `DECISION_EMPTY`。

**明确不做：**

- 最低抽样概率、探索奖励、对真实模型的特殊保护；  
- 修改 Θ_W 或 χ² 阈值；  
- 将 shadow 权重事件当作证据排除；  
- 修改 `pilot_fi_anchor` 源码。

---

## 评分规则统一表述

| 臂 | 资格集 E | 排序键 |
|---|---|---|
| A | `alive` | `w_surv`（≡ 在 E 上对 raw 支持归一化后的质量） |
| B/C | `not excluded` | `w_all`（argmax 与在 E 上重归一化相同） |

三者均为「资格集上的支持权重最大者」；差异**仅**来自资格政策（及 C 的数据轨迹）。

---

## 失败与中止码（冻结）

| 码 | 含义 | 计入 |
|---|---|---|
| `DECISION_EMPTY` | 终局 E=∅，无首位模型 | Primary 失败（无有限 RMSE 时用约定惩罚，见评估协议） |
| `ABORT_EMPTY_ELIGIBLE` | C 中途 E=∅，无法继续合法分配 | 该臂 run 中止；Primary 失败 |
| `ABORT_ZERO_WEIGHT_MASS` | E 非空但权重质量和 ≤0 | 同上 |
| `TRUTH_OPERATIONAL_EXCLUSION` | 真实 hump 被 χ² 排除 | Secondary 失败计数；**不是**设计漏洞 |

禁止将上述情况静默转化为“任选一模型继续”。
