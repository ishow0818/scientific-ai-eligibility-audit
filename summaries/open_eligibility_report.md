# Open Eligibility 事后终局对照（冻结 Stage-2，种子 201–240）

性质：**事后终局重算**。复用 Native 观测、最终拟合参数与 `w_all`；
不新增种子、不重新采样、不重新拟合、不改写 `stage2_formal` 冻结结果。

## 终局规则

| 规则 | 选择范围 |
|---|---|
| Native | 未被历史剪枝的模型（`alive`） |
| Open Eligibility | 全部五个已拟合模型 |
| Decision-Only | 未被操作性证据规则排除的模型（`excluded=False`） |

## 汇总

| 指标 | Native | Open Eligibility | Decision-Only |
|---|---:|---:|---:|
| 真实模型选择 | 37/40 | 40/40 | 39/40 |
| 平均预测 RMSE | 0.1354 | 0.0847 | 0.1033 |
| 中位预测 RMSE | 0.0743 | 0.0743 | 0.0743 |

### 配对 ΔRMSE（惩罚尺度；正值=前者更差）

- Native−Open：{'delta_rmse_penalty_median': 0.0, 'delta_rmse_penalty_mean': 0.05075533784365279, 'n_positive': 3, 'n_negative': 0, 'n_zero': 37}
- Native−Decision-Only：{'delta_rmse_penalty_median': 0.0, 'delta_rmse_penalty_mean': 0.032090968194265185, 'n_positive': 2, 'n_negative': 0, 'n_zero': 38}
- Open−Decision-Only：{'delta_rmse_penalty_median': 0.0, 'delta_rmse_penalty_mean': -0.018664369649387606, 'n_positive': 0, 'n_negative': 1, 'n_zero': 39}

### 选择差异种子

- Open ≠ Native：[208, 224, 232]
- Open ≠ Decision-Only：[208]
- Decision-Only ≠ Native：[224, 232]
- Open 与 Decision-Only 全队列相同：False

### 全池赢家与证据/剪枝标签

- 全池赢家已被证据规则排除：1/40
- 全池赢家已被历史剪枝：3/40

真模型选择配对：{'A_yes_O_no': 0, 'A_no_O_yes': 3, 'O_yes_B_no': 1, 'O_no_B_yes': 0, 'A_yes_B_no': 0, 'A_no_B_yes': 2}

重建一致性（应用原规则重算赢家）：{'native_all': True, 'decision_all': True}

## 解释

Open Eligibility and Decision-Only differ on some seeds; inspect per-seed cases for evidence-gate help vs harm (no presupposed direction).

## 差异个案

### 种子 208
- 选择：Native=`quad`，Open=`hump`，Decision-Only=`quad`
- 真值选中：N=False / O=True / B=False
- RMSE：N=0.8292017328784653 / O=0.08262694690296106 / B=0.8292017328784653
- 全池赢家 excluded=True，pruned=True
- 角色：Evidence gate harms relative to Open: Decision-Only rejects full-pool winner (or otherwise selects differently) and loses truth

### 种子 224
- 选择：Native=`quad`，Open=`hump`，Decision-Only=`hump`
- 真值选中：N=False / O=True / B=True
- RMSE：N=0.7517157109607586 / O=0.1447737015451857 / B=0.1447737015451857
- 全池赢家 excluded=False，pruned=True
- 角色：Open==Decision≠Native: gain/loss vs Native attributable to reopening eligibility; evidence gate does not further change winner

### 种子 232
- 选择：Native=`quad`，Open=`hump`，Decision-Only=`hump`
- 真值选中：N=False / O=True / B=True
- RMSE：N=0.7685198598590994 / O=0.09182314150406487 / B=0.09182314150406487
- 全池赢家 excluded=False，pruned=True
- 角色：Open==Decision≠Native: gain/loss vs Native attributable to reopening eligibility; evidence gate does not further change winner

## 逐种子一行表

| seed | Native | Open | Decision | N✓ | O✓ | B✓ | Open=Dec | winner_excl |
|---:|---|---|---|---|---|---|---|---|
| 201 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 202 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 203 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 204 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 205 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 206 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 207 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 208 | quad | hump | quad | 0 | 1 | 0 | 0 | 1 |
| 209 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 210 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 211 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 212 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 213 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 214 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 215 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 216 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 217 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 218 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 219 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 220 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 221 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 222 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 223 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 224 | quad | hump | hump | 0 | 1 | 1 | 1 | 0 |
| 225 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 226 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 227 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 228 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 229 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 230 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 231 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 232 | quad | hump | hump | 0 | 1 | 1 | 1 | 0 |
| 233 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 234 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 235 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 236 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 237 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 238 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 239 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
| 240 | hump | hump | hump | 1 | 1 | 1 | 1 | 0 |
