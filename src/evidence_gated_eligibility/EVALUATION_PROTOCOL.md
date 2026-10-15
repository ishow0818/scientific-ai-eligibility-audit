# EVALUATION_PROTOCOL — 独立评估与正式队列

## 1. 独立预测网格（冻结）

**原则：** 不在任何臂的可测量候选池中；不进入拟合；全 seeds × 全臂相同。

| 项 | 冻结定义 |
|---|---|
| 候选可测池 | `idx ∈ {0,…,400}`，`x = linspace(0,10,401)`（原 `N_CAND`） |
| 评估点 | **离网格**中点：`x_k = (grid[k]+grid[k+1])/2`，`k=0..399`（共 400 点） |
| 可测性 | 评估点 **无**整数 `idx`；`World.y` / allocate **永不**查询这些 x |
| 真值 | 无噪声：`f*(x) = TRUTH.predict(x, TRUTH_THETA)` |
| 模型预测 | 该臂终局 `arm_theta[incumbent]`（或 B 重选后的 theta）；`incumbent is None` → 无预测 |
| Primary 公式 | `RMSE = sqrt(mean_k (f*(x_k) - f̂(x_k))²)` |

**不做：** 从 401 格点中预留子集（会改变 A 相对正式 Native 的可测空间）。  
**不做：** 用带噪 `y` 作 holdout（Primary 明确为无噪声真值 RMSE）。

常量名（实现时）：`EVAL_X_MIDPOINTS`，写入每条 run 记录的 `eval_protocol_version`。

## 2. 终点指标

### Primary（科学发现质量）

- 各臂最终所选模型在 `EVAL_X_MIDPOINTS` 上的 **无噪声真值 RMSE**。  
- `DECISION_EMPTY` / `ABORT_*`：该臂该 seed 记为 Primary **无效**；汇总时：
  - 主分析：报告有效 RMSE 的配对差 + 失败率；
  - 敏感性：失败 RMSE 记为约定上界惩罚 `RMSE_FAIL = RMSE of zero-predictor vs truth`（即 `sqrt(mean f*^2)`），**预先冻结**，非调参。

### Secondary

| 指标 | 定义 |
|---|---|
| 真模型最终选择率 | `incumbent == hump` 的 seed 比例（分母=20 或正式 40；ABORT 计未选中） |
| 真模型资格退出率 | A：`alive[hump]=False`；B/C：`excluded[hump]=True` 或（C）中途因排除失去资格 | 

对 B：资格退出指终局 `excluded[hump]`（轨迹同 A）。  
对 C：报告首次 `excluded[hump]` 轮次及是否曾失去 allocate 资格。

### Cost / 描述性（非成功标准）

- 终局仍资格内的错误模型数 `|E ∩ FALSE|`  
- 实际测量数（应为 N0+R·M=135，ABORT 则更少）  
- wall-time / 拟合调用次数（若日志可得）  
- **明确：保留更多候选 ≠ 成功**

### 操作性证据（非 Primary）

- 真模型被 χ² 排除次数（`TRUTH_OPERATIONAL_EXCLUSION`）  
- 标注 χ² = `OPERATIONAL_ONLY`

## 3. 配对设计与统计

| 项 | 规则 |
|---|---|
| 噪声配对 | 同一 `World(seed)` 供 A 与 C；B 复用 A |
| Alloc RNG | A 与 C：`SeedSequence([MASTER_SALT, seed, ARM_CODE_NATIVE, RNG_ALLOC, t])`；**独立** `Generator` 实例（CRN，同 opp-ablation v0.2） |
| Arm 码 | 资格门控包内常量 `ALLOC_ARM_CODE = 0`（与正式 Native 相同），**不**改 `pilot_fi_anchor.config` |
| Fit RNG | 每臂独立 `Arm` 实例各自 `fit_rng(seed)`（同正式：同 seed 同初始序列；轨迹分叉后自然分叉） |
| 主对比 | A vs B（纯决策资格）；A vs C（闭环资格）；B vs C（离线 vs 闭环） |
| 推断单位 | **seed**；报告配对 ΔRMSE 中位数 / 均值、符号检验或 Wilcoxon；Wilson CI 用于比率 |
| 依赖 | 不把同 seed 多候选当独立试验 |

## 4. 固定种子计划（本 Stage **不执行**）

| 队列 | Seeds | 用途 |
|---|---|---|
| 单元 / Native 复现 | `{1, 3, 20}` 等小集 | 实现阶段测试 |
| Smoke | `{201, 202, 203}` | 实现后短跑（Stage 1）；**本 Stage 禁止跑** |
| **正式独立队列** | **`201–240`（40 seeds）** | Stage 2 正式；与历史 1–20 / 101–120 **不相交** |
| 禁止 | 按已有结果挑 seed；用 1–20 当正式确认集 | |

正式分析预注册对比：Primary 关注 `median(RMSE_A - RMSE_C)` 与 `median(RMSE_A - RMSE_B)` 及失败率；不在看结果后改网格或阈值。

## 5. 记录字段（每 seed）

```
seed, arm ∈ {native, decision_only, full_evidence_gate}
incumbent, eligible_set, excluded, alive_or_shadow
rmse_eval_noiseless, primary_status ∈ {OK, DECISION_EMPTY, ABORT_*}
n_measured, n_false_eligible_final
truth_selected, truth_excluded_operational
t_first_site_fork_vs_native (C only)
wall_s (optional)
```
