# Evidence-Gated Eligibility — Stage 2 正式报告

版本：`ege-stage2-0.1.0`  |  seeds **201–240** (n=40)
χ²：`OPERATIONAL_ONLY`  |  未改阈值 / 未改 `pilot_fi_anchor` / 未改论文

## 运行环境（结果绑定）

- platform: `Windows-10-10.0.19045-SP0`
- Python: `3.12.10 (tags/v3.12.10:0cc8128, Apr  8 2025, 12:21:36) [MSC v.1943 64 bit (AMD64)]`
- NumPy: `2.5.0`  |  SciPy: `1.17.1`
- executable: `D:\home\venv\Scripts\python.exe`

> Stage1 已记录跨 OS 数值敏感性；本正式结果仅对该环境有效。

## Primary：独立网格无噪声 RMSE

### native
- 失败 k=0/40；率 Wilson95=[0.0, 0.0, 0.08762453925039232]
- 失败类型：{}
- 有限 RMSE：n=40；median=0.07434531141261147；mean=0.1354327317765893
- 惩罚 RMSE（失败→RMSE_FAIL）：median=0.07434531141261147；mean=0.1354327317765893
- 终局错误模型资格数均值：0.075

### decision_only
- 失败 k=0/40；率 Wilson95=[0.0, 0.0, 0.08762453925039232]
- 失败类型：{}
- 有限 RMSE：n=40；median=0.07434531141261147；mean=0.10334176358232412
- 惩罚 RMSE（失败→RMSE_FAIL）：median=0.07434531141261147；mean=0.10334176358232412
- 终局错误模型资格数均值：0.175

### full_evidence_gate
- 失败 k=0/40；率 Wilson95=[0.0, 0.0, 0.08762453925039232]
- 失败类型：{}
- 有限 RMSE：n=40；median=0.07433516631892698；mean=0.08297215713044082
- 惩罚 RMSE（失败→RMSE_FAIL）：median=0.07433516631892698；mean=0.08297215713044082
- 终局错误模型资格数均值：0.125

## 配对 ΔRMSE（惩罚尺度；正值=前者更差）

- A−B：{'delta_rmse_penalty_median': 0.0, 'delta_rmse_penalty_mean': 0.032090968194265185, 'n_positive': 2, 'n_negative': 0, 'n_zero': 38}
- A−C：{'delta_rmse_penalty_median': 0.0, 'delta_rmse_penalty_mean': 0.052460574646148485, 'n_positive': 8, 'n_negative': 5, 'n_zero': 27}
- B−C：{'delta_rmse_penalty_median': 0.0, 'delta_rmse_penalty_mean': 0.0203696064518833, 'n_positive': 8, 'n_negative': 5, 'n_zero': 27}

## Secondary

- native: truth_selected=37/40 [0.925, 0.8013546984090248, 0.9741644432281419]；truth_excl_op=1；truth_elig_lost=3 [0.075, 0.025835556771858226, 0.19864530159097524]
- decision_only: truth_selected=39/40 [0.975, 0.8711834051199223, 0.9955732825922052]；truth_excl_op=1；truth_elig_lost=1 [0.025, 0.0044267174077949195, 0.1288165948800778]
- full_evidence_gate: truth_selected=40/40 [1.0, 0.9123754607496077, 1.0]；truth_excl_op=0；truth_elig_lost=0 [0.0, 0.0, 0.08762453925039232]

真模型选择配对差：{'A_yes_B_no': 0, 'A_no_B_yes': 2, 'A_yes_C_no': 0, 'A_no_C_yes': 3}

## 机制解读边界

- Primary 看发现质量（RMSE），不把「保留更多候选」当成功。
- B=离线终局资格；C=闭环资格；差异含数据轨迹效应。
- 真模型操作性排除计失败（非 oracle）。

**未修改论文。**
