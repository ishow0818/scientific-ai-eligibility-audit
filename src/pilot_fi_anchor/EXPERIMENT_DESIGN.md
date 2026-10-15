# 假识别锚点闭环实验 — 实验设计与冻结参数 v1.1.2

**状态**: v1.1.2（证据 sequential Bonferroni 修复）。v1.1.1 为已被修复替代的探索性 20-seed 批次；v1.1.2 confirmatory 20-seed 已完成，冻结输出见 ../outputs/pilot_fi_anchor/。
任何参数变更须先改本文档、升版本号、重新评审。

---

## 1. 目标

不是开发新算法。在同一个可控 scientific hypothesis discovery 系统中闭合完整证据链:

```
recursive allocation
  → evidence-compatible alternative 提前消失
  → matched Neutral 中该 alternative 被保留 / 延迟消失
  → elimination 时 evidence 尚未排除它
  → 后续 discriminative evidence 才真正排除它
```

同时测量闭环对 representation 局部扰动的 empirical local response **g**
(secondary),用于检验真实闭环中是否存在 representation perturbation
amplification。**不把算法超参数映射为 α、μ**;γ、θ_w 等只是闭环自身的
动力学参数;**不将 g=1 解释为 R_id=1 的直接经验估计**(见 §8)。

## 2. 系统定义

### 2.1 输入域与观测

- 一维输入 x ∈ [0, 10];候选测量点 X_cand = 401 个等距网格点(间距 0.025)。
- 观测 y = f*(x) + ε,ε ~ N(0, σ²),**σ = 0.5 已知**(证据判据以已知 σ 为准)。

### 2.2 真值(ground truth)

峰值响应族(hump):y = A·exp(−(x−μ)²/(2s²)),θ* = (A=8, μ=4.5, s=2.5)。

| x | 0 | 0.5 | 1 | 2 | 3 | 4 | 4.5 | 5.5 | 8 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| f* | 1.58 | 2.23 | 3.00 | 4.85 | 6.68 | 7.84 | 8.00 | 7.39 | 3.00 | 0.71 |

结构要点:**[0.5, 2] 上全部候选族的最佳拟合与真值偏差 ≤ ~0.35(σ 以内),
证据兼容;在 [5, 10] 上假族偏差 ≥ 1.5 量级,必被排除**。初始观测只覆盖
[0.5, 2],于是早期多机制证据兼容、未充分测量区域预测分歧 — 即锚点处的
under-identification。

### 2.3 机制族(5 个,均可解释)

| id | 名称 | 表达式 | 参数(边界) | 早期行为 | 未测量区行为 |
|---|---|---|---|---|---|
| hump | 峰值响应 | A·e^{−(x−μ)²/2s²} | A∈(0.05,20), μ∈[0,10], s∈(0.3,6) | 上升沿 | 过峰回落 → ≈0.7 |
| affine | 线性累积 | a + b·x | a∈(−5,15), b∈(0.05,5) | 线性上升 | 线性外推 → ≈19 |
| pow | 幂律增长 | α·x^β | α∈(0.05,20), β∈[0.1,3] | 凹上升 | 次线性外推 → ≈10–14 |
| expsat | 指数饱和 | A(1−e^{−x/τ}) | A∈(0.05,20), τ∈(0.3,8) | 凹上升 | 饱和平台 → ≈6–7 |
| quad | 二次加速 | a + b·x + c·x² | a∈(−5,20), b∈(−5,10), c∈(−1,3) | 凸上升 | 二次发散 → ≫10 |

- 真值族 = hump(在集合内,参数恰好为真);假族 = affine / pow / expsat / quad,
  全部单调,无法拟合回落段 → 最终必被证据排除。
- 参数数 2–3;证据判据按各自自由度 p_h 处理(见 §5),支持分不额外加复杂度罚项。

### 2.4 初始观测(所有 seed、两臂完全相同)

n0 = 10 个点,网格索引 {20, 27, 33, 40, 47, 53, 60, 67, 73, 80}
(即 x = 0.5, 0.675, …, 2.0);其噪声 ε₀ 由 seed 20260921 生成**一次**、
**所有 seed 与两臂共用** → "每个 seed 从完全相同的初始 observations 分叉" 按最严格
口径实现:分叉点状态逐位相同。

### 2.5 匹配方案(除 allocation 外全部匹配)

- 每个 seed 预生成 401 点噪声场(`SeedSequence([2026, seed, RNG_NOISE=1])`);初始点处
  覆盖为共享 ε₀。
- 任一点 (seed, x) 的观测 y 完全确定 → **两臂测同一点必得相同 y**(代码断言);
  共享初始观测跨 seed 全等(断言)。
- 数据、预算、σ、拟合器、候选机制、RNG 派生、**PUBLIC evidence 规则**在两臂
  完全一致;**唯一结构性差异 = allocation 规则**(见 §3)。
- 已获得 measurement → **PUBLIC** → 全部 hypothesis 可更新;Native 的提名者
  credit 仅作 provenance,**不得**限制谁看到数据。

## 3. 两臂定义(allocation)

### 3.1 Native(support 决定下一轮 allocation)

- 每轮 m = 5 个新点,无重复测量。
- **提名**:每个存活假设 h 用其 stream 拟合的残差场 r̂_h(x)给出效用
  u_h(x) = exp(−(r̂_h(x)/σ)²),对未测点排名,提名前 5。
- **选择**:以存活假设的 w(幸存者集内归一化)为概率无放回抽 5 个提名。
- **Provenance(credit)**:记录提名假设 h,**但不**限制 stream 访问;测到的点
  进入**全部** hypothesis stream(PUBLIC evidence,见 §3.3)。

### 3.2 Neutral(切断 support → future opportunity 依赖)

- 固定扫掠,与 support 无关:第 j 个点 = 网格索引 84 + ⌊316·(j−1)/124⌋,
  j = 1..125,即 x 从 2.1 均匀升序扫到 10.0,每轮 5 点,全域覆盖。
- credit 记为 PUBLIC;测到的点同样进入全部 hypothesis stream。

### 3.3 共同机制(两臂完全一致)

**PUBLIC evidence**:measurement acquisition → 全部 hypothesis stream → 全部
可更新 support 与 arm-wide evidence。

stream → S → w、淘汰规则、拟合器、证据判据、RNG 派生、记录 schema 在两臂
逐行相同;**唯一结构性差异 = allocation 规则**(Native adaptive vs Neutral
fixed sweep)。

> **评审要点**:FI 机制载体是 support-dependent **allocation**,不是 private
> evidence stream。credit 仅 provenance。

## 4. 算法支持(algorithmic support)

- 第 t 轮(本轮数据入库后):
  S_h(t) = Σ_{i ∈ stream_h} γ^{t−t_i} · log N(y_i | f_h(x_i; θ̂_h(t)), σ²),
  **γ = 0.85**(近因加权)。
  θ̂_h(t) 由 h 的 stream 数据拟合(MLE,warm start)。
- w = softmax(S)(温度 1,全体 5 族;实现用 max 减法防下溢)。
- **淘汰**:t ≥ 1 时,若某存活假设在幸存者集内归一化权重 < θ_w = **0.02** →
  永久淘汰(不复活);淘汰后仍逐轮拟合、记录(反事实支持与 t_excl 追踪),
  但不再参与提名(Native)/不再获得新机会;Neutral 的公开归属照常计入其记录。
- **拟合**:scipy least_squares,残差按 σ 归一;正参数取 log 参数化;首轮 3 个
  seeded 起点取最优,其后 warm start(拟合器确定性,见 §9)。

> γ 与 θ_w 是闭环自身的动力学参数,不是 α、μ 的映射;灵敏度分析列为 Phase 2
> (只报告、不作 gate、不调参,见 §12)。

## 5. 独立冻结的证据判据(evidence criterion)

与 algorithmic support 无任何耦合,只使用该臂**全部**观测与已知 σ:

- 每轮、每假设 h:用该臂全部数据拟合 θ̂_h^arm,得 RSS_h。
- 违规:stat = RSS_h / σ² > χ²_{1−α}(n_arm − p_h),
  **α = 0.05/(5·R) = 0.0004**(v1.1.2: 5 族 Bonferroni × R 轮 sequential
  Bonferroni;不做 post-hoc 调阈值);2-round persistence 不变;端点仍取首次确认。
- **excluded 状态 = 连续 2 轮违规**(向后持久:violated(t) ∧ violated(t−1));
  t_excl = 首个 excluded 轮;至第 R 轮仍未出现 → 记截尾(哨兵 R+1)。
- 证据兼容 = 非 excluded。

## 6. 预算与规模(最小 pilot)

- **20 seeds**(seed id 1..20);**R = 25 轮**;每轮 **m = 5** 个新点;
  每臂 10 + 125 = 135 点;CPU-only,预计单核数分钟内跑完(见 KILL-B5)。

## 7. 记录 schema

每个 seed 输出一个 JSON(含两臂 + 扰动测量):

```
rounds[arm][t]: per h {S, w_all, w_surv, alive, t_elim, stream_n,
                       rss, stat, crit, violated, excluded, t_excl}
                + {incumbent, n_arm, sites:[idx]}
sites[arm]:     {t, idx, x, y, credit: h | "PUBLIC"}
perturb:        {t, arm, h, g, cos, norm_pert, norm_delta}
meta:           {seed, config(冻结快照), version}
```

## 8. 局部扰动实验(empirical local gain — **secondary**)

- 时刻:每轮 t = 1..R−1,两臂,在 t 轮 support 更新之后。
- 目标:每个**存活的非 incumbent** 假设 h;方向 d = e_h − w_all;
  w_pert = w_all + δ·d,**δ ∈ {0.01, 0.025, 0.05}**(预注册幅度)。
- **CRN 反事实分支**:baseline 与 perturbed 下一步共用同一 `alloc_rng(seed, arm, t+1)`
  的 fork(`fork_rng`);唯一允许差异 = representation 扰动。
- **增益**:g = ‖w_pert_next − w_base_next‖₂ / ‖w_pert − w_base‖₂;
  δ=0 时两 branch bit-identical(单元测试断言)。
- **Neutral 零增益对照**:allocation 不看 w → g ≡ 0(KILL-B4),但**不能**作为
  CRN 正确性的唯一测试。
- **定位**:g 是 empirical local response / perturbation amplification
  diagnostic,**不是** α、μ、R_id 的直接估计;不作 PASS gate。本实验测量 g
  以检验真实闭环是否存在 representation→opportunity 局部放大,**未建立**
  g=1 ↔ R_id=1 的严格映射。

## 9. 冻结参数总表

| 参数 | 值 | 参数 | 值 |
|---|---|---|---|
| 域 | x ∈ [0,10] | 网格 | 401 点(0.025) |
| 真值 | hump (8, 4.5, 2.5) | σ | 0.5(已知) |
| 初始观测 | 10 点,idx {20,27,33,40,47,53,60,67,73,80} | ε₀ | seed 20260921,跨 seed 共享 |
| seeds | 1..20 | 轮数 R | 25 |
| 每轮新点 m | 5 | 每臂总点 | 135,无重复 |
| γ(近因) | 0.85 | θ_w(淘汰) | 0.02,永久、不复活 |
| α(证据) | 0.05/(5·R)=0.0004 | excluded 持久 | 连续 2 轮违规 |
| δ(扰动) | {0.01, 0.025, 0.05}; **主报告 δ=0.05 冻结** | 截尾哨兵 | R+1 |
| Native 提名 | 幸存者残差场,前 5 | Native 选择 | ∝ w(幸存者),无放回 |
| Neutral 扫掠 | idx_j = 84 + ⌊316(j−1)/124⌋,j=1..125 | evidence | PUBLIC(两臂) |
| 拟合 | least_squares,残差/σ,log 正参数,warm start | RNG/CRN | alloc_rng + fork_rng |
| focal victim | 仅代表性案例(tie:族序) | 截尾 | t_excl = R+1 |

## 10. 端点定义

- **focal victim V_s**(descriptive only):Native 中最先被淘汰的假族;用于轨迹/
  代表性案例,**不**决定 primary PASS。
- **E1 无证据支持的淘汰(primary, seed-level)**:该 seed 存在 ≥1 个 auditable
  false-family 事件,在 t_elim 时刻 Native 证据仍兼容(unsupported)。
  **Secondary(event-level)**:全部 auditable 淘汰事件中 unsupported 比例。
- **E2 时间缺口 temporal FI(primary gate)**:
  **ΔT_FI = t_excl^Native − t_elim^Native**,同一 alternative、同一 Native 轨迹。
  **PASS-A3 分母 = 全部 unsupported events**;`frac(ΔT_FI≥1)≥60%`。
  截尾事件(t_excl 未出现):若观测 horizon **R > t_elim+1**,计作 ΔT_FI≥1。
  **median_finite_dFI**(仅 finite t_excl)为 descriptive,不作硬 gate。
  **Supporting**:ΔT^cross = t_excl^Neu − t_elim^Native(跨臂因果对比,非 primary)。
- **E3 因果救援(separate endpoint)**:对 unsupported 事件,Native 在 t 淘汰 h,
  Neutral 在**同一时刻**仍存活(t_elim^Neu > t 或尚未淘汰)。
- **次级**:Native 最终 truth recovery(描述性,**非** PASS gate);Neutral 收敛率;
  全事件表;ḡ(t) 增益剖面(secondary)。

## 11. PASS / KILL gates(预注册,结果出来后不得修改)

**KILL(B 类,硬门槛 — 任一失败 = pilot 无效,修复后重跑,不得据以做任何声称):**

| 编号 | 条件 | 阈值 |
|---|---|---|
| KILL-B1 | Neutral 最终 incumbent = hump(证据机制自洽) | ≥ 18/20 seeds |
| KILL-B2 | 真值被证据误排除 | Neutral 0 臂 / Native ≤ 1 臂 |
| KILL-B3 | 第 0 轮 5 族全部证据兼容(under-identification 前提成立) | ≥ 18/20 seeds |
| KILL-B4 | 匹配断言:共享点 y 全等;初始观测跨 seed 全等;Neutral 增益 ≡ 0 | 全部成立 |
| KILL-B5 | 全 pilot 运行时间(单核 CPU) | ≤ 1 小时 |

**PASS(A 类,科学声称 — 全部满足 = 链条闭合;部分满足 = 报告为部分证据;
全不满足 = 诚实零结果,升级 v2 前不得静默调参):**

| 编号 | 条件 | 阈值 |
|---|---|---|
| PASS-A1 | seed-level: ≥1 unsupported false-family elimination(E1) | ≥ 8/20 seeds |
| PASS-A2 | unsupported 事件上 Neutral 同期仍存活(E3) | ≥ 60% |
| PASS-A3 | unsupported 事件上 frac(ΔT_FI≥1) | ≥ 60% |
| DESC-A4 | Native 最终 truth recovery(描述性) | 无 gate |

**增益 ḡ**:secondary only;不作 gate。
**模糊带**:A1 落在 (2/20, 8/20) 之间 → 结论为 ambiguous,升版 v2(明确更动,
重走评审),不得把 Phase 2 灵敏度结果当作调参许可。

## 12. 预期动力学与已知风险(待 gates 检验,非预设结论)

预期时间线(假设链条成立时):

| 轮 | Native | Neutral |
|---|---|---|
| 0 | 全族兼容,w 均匀 | 同左(完全相同的初始观测) |
| 1–8 | support-dependent allocation → 测量轨迹分化 → support 差异累积 → 某假族最先被淘汰(淘汰时证据兼容) | 固定扫掠;全族存活 |
| 9–15 | incumbent 继续沿 adaptive 轨迹测量,不触判别区 | 扫掠进入 x ≥ 5 → 假族被证据排除 |
| 15–25 | 可能出现 unsupported elimination 持续至 horizon | 收敛 hump |

已知风险 / 开放问题:

1. **allocation 不对称(§3)是本设计的机制核心** — PUBLIC evidence 已统一;
2. γ、θ_w 冻结但灵敏度未测(Phase 2 只报告);
3. Native 中真值(hump)可能被淘汰 — 这是比"假族被提前淘汰"更强的 FI 表现,
   列为次级端点如实报告;
4. 幂律在 x→0 的奇异:若 incumbent 向 x<0.5 挖掘,pow 的 t_excl^N 可能有限
   (E2 按截尾方案处理,如实报告);
5. g 为 empirical local response(§8),不声称 g=1 ↔ R_id=1 的直接经验映射;
6. v1.1.2 的 20-seed confirmatory output 已归档；后续任何算法、阈值或机制修改均须升版本并重新评审，不能以现有结果为依据调参。

## 13. 代码结构

```
pilot_fi_anchor/
  EXPERIMENT_DESIGN.md   # 本文件(设计冻结稿)
  README.md              # 核心命题、KILL 规则、运行顺序(项目惯例)
  config.py              # 冻结参数(frozen dataclass,单一事实来源)
  mechanisms.py          # 5 个机制族 + 真值 + 拟合空间映射
  world.py               # 噪声场、共享初始观测、匹配断言
  fitting.py             # least_squares 拟合、残差场、log-lik
  loop.py                # Arm(Native/Neutral):一轮闭环 + support + 淘汰 + 证据
  perturbation.py        # CRN 局部扰动 + 实证增益 g (secondary)
  evidence_calibration.py # 证据判据 sanity check
  rng.py                 # SeedSequence + fork_rng (CRN)
  recorder.py            # per-seed JSON(schema 见 §7)
  metrics.py             # 端点 E1–E3 + 次级 + 截尾处理 + 精确二项 CI
  gates.py               # KILL-B1..B5 / PASS-A1..A4
  analysis.py            # 汇总 CSV / endpoints.json / gates.json
  __main__.py            # CLI:python -m pilot_fi_anchor [--seeds] [--dry] …
  tests/                 # pytest(不运行 pilot,只测单元不变量)
```

运行(评审通过后):

```bash
pytest pilot_fi_anchor/tests -q
python -m pilot_fi_anchor --calibrate                 # 证据判据 sanity check
python -m pilot_fi_anchor --dry                      # 1 seed × 4 轮,代码自检
python -m pilot_fi_anchor --seeds 1..20              # 正式 pilot
python -m pilot_fi_anchor --seeds 1..20 --no-perturb # 可选:无扰动加速
```

依赖:numpy、pandas、scipy(least_squares、chi2)、pytest(已在
requirements.txt 追加 scipy)。

**确定性**:所有随机数经 SeedSequence([2026, seed, role, …]) 显式派生;拟合
warm start 确定性;同一 seed 重跑逐位一致。
