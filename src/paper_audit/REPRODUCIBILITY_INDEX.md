# 当前稿件复核入口

2026-10-14。本地材料索引，不是已完成的公开发布包。Open Eligibility 已完成；它是同一冻结队列的事后终局重算，不是新的独立确认实验。

## 原有 40 次资格干预记录的只读检查

在项目根目录执行：

    D:\home\venv\Scripts\python.exe -B paper_audit/verify_frozen_eligibility.py

脚本读取原 stage2_formal 中 seed 201–240，检查 A/B 观测位置、逐轮记录及最终拟合参数相同，重新计算三个既有实验臂的独立网格预测 RMSE，核对正确选择数及两个终局选择变化案例，并向标准输出返回输入和相关代码的 SHA-256。

该入口只检查原 A/B/C，不重新采样、拟合或模拟，也不修改冻结文件。它不是全部实验的一键复现。当前哈希支持之后的完整性检查，不证明文件历史上何时冻结；其所调用的预测实现仍需依赖所记录的软件环境。

## Open Eligibility 事后终局对照

实现：evidence_gated_eligibility/open_eligibility_posthoc.py；结果：evidence_gated_eligibility/outputs/open_eligibility_posthoc。只读一致性测试：

    D:\home\venv\Scripts\python.exe -B -m pytest evidence_gated_eligibility/tests/test_open_eligibility_frozen.py -q -p no:cacheprovider

审查时 44 项测试通过，并从原 JSON 独立重算全池赢家及 RMSE，核对没有最高评分并列。Native/Open/Decision-Only 正确选择为 37/40、40/40、39/40；Open 纠正 208、224、232，Decision-Only 仅纠正后两例。Open 与 Decision-Only 只在 208 不同：真实模型已被操作性证据规则排除。Open 相对 Native 的 RMSE 改善为 3 次、不变 37 次，中位差为零。

冻结锁定文件检查结果漂移，不是独立真值验证或预注册证据。运行实现的 main 入口会重写派生报告；只读复核应使用上述测试，不重新生成报告。原 A/B/C 数据保持不变。

## 各队列与材料

| 内容 | 统计范围 | 本地入口及边界 |
| --- | --- | --- |
| 最小动力学 | 原参数网格与种子 | identifiability_dynamics_final/config.py；包内 results/final_verdict.json |
| Anchor 主实验 | seeds 1–20 | pilot_fi_anchor；outputs/pilot_fi_anchor |
| 真实模型丢失扩展 | seeds 21–40 | pilot_truth_loss/FAILURE_MODE_V2_PREREG.md；outputs/pilot_truth_loss_v2；不采用更宽种子聚合 |
| 机会反馈消融 | 复用 seeds 1–20 | pilot_opp_feedback_ablation；outputs/pilot_opp_feedback_ablation_formal_v2；不是新的独立主队列 |
| 重新进入干预 | seeds 121–140 | 主稿 meth:reentry；公开发布时仍需核定该队列唯一输出入口 |
| A/B/C 资格干预 | seeds 201–240 | evidence_gated_eligibility/outputs/stage2_formal |
| Open Eligibility 事后对照 | 同一 seeds 201–240，不是新队列 | evidence_gated_eligibility/outputs/open_eligibility_posthoc |
| 资格因果审计 | 上述既有队列 | evidence_gated_eligibility/outputs/stage2_causal_audit |
| χ² 可靠性审计 | 历史记录与附加检查，勿合称全新队列 | outputs/anchor_chi2_reliability_audit |
| CoFI 覆盖 | seeds 401–410，186 条候选—运行记录 | analysis/cofi_paired_coverage.py 及同名 JSON |
| ARROWS 局部门控 | 5 个筛选事件、4 条候选路线 | arrows_phase2e_gate_verification/outputs |
| ARROWS 来源与方向 | 上述筛选案例 | arrows_lowT_provenance_audit/outputs；arrows_strict_directional_audit/outputs |

不同队列不合并为统一发生率。原 19 点预测评价与 Native 测量有重叠，不应称严格留出；新资格干预采用 400 个不可被测量的网格中点，但仍是同一合成系统内的预测评价。

AEA 空白记录及三个证据层次的填写示例见同目录 AEA_TEMPLATE.md。示例不是检测性能评估。

## 发布前仍须完成

- 将每个结果绑定唯一入口、源代码版本、配置、依赖及原始输入；补全重新进入队列入口。
- 保留已有时间线和修改记录，不根据当前文件哈希反推预注册时间。
- 资格干预记录版本为 ege-stage2-0.1.0；已记录环境为 Windows、Python 3.12.10、NumPy 2.5.0、SciPy 1.17.1。不可据此代替其他实验的环境清单。
- 核对第三方数据、图谱与代码的再分发许可，特别保留 ARROWS 未验证低温记录的来源标记。
- 完成版本化公开归档、访问条件和持久标识，核对论文中的路径与发布包一致。当前未声明这些步骤已经完成。
