# Opportunity-Feedback Ablation — 源码审计

**日期：** 2026-10-12  
**范围：** `pilot_fi_anchor/loop.py` Native 选点路径；不改正式阈值/论文。

## 结论：`ISOLATABLE`

支持权重对**下一轮实验机会分配**的影响可在不改动拟合、支持更新、剪枝与 χ² 的前提下隔离。

## Native 完整选点流程（每轮 `t≥1`）

`Arm.step` 顺序（`loop.py`）：

1. **分配** `_allocate_native(rng, w_full)`  
   - 默认 `w_full = self.w_all`（可用 `w_override` 覆盖，扰动实验已使用该钩子）。  
2. `_ingest`：新点进入**所有**假说 stream（PUBLIC）。  
3. `_refit_streams` → `_update_support`：重算 `S` / `w_all` / `w_surv`。  
4. `_check_elimination`：`w_surv < Θ_W=0.02` → `alive=False`。  
5. `_update_evidence`：χ² → `violated` / `excluded`（**不**改 `alive`）。  
6. `_record`。

### `_allocate_native` 内部结构

| 步骤 | 是否读支持权重 | 说明 |
|---|---|---|
| 存活集合 `alive` | 否（读 `alive` 标志） | 已退出候选不提名 |
| 未测合法空间 | 否 | `idx ∉ measured` |
| 各存活假说提名排序 `ranked[h]` | **否** | `u(x)=exp(-(r̂/σ)²)`，依赖 stream 拟合 |
| **proposer 多项式抽样** | **是** | `probs ∝ w_full[h]`（在 alive 上归一化） |
| 按提名列表取未占用点 | 否 | 最终选点 |

因此：**机会分配反馈** = “当前 `w_all`（经 override）决定谁获得下一次测量提名机会”。  
**不是**提名效用函数本身，也不是剪枝/证据规则。

## 消融设计

| 臂 | 分配权重 | 其余 |
|---|---|---|
| Native | `w_override=None` → `self.w_all`（原实现） | 不变 |
| No-Opportunity-Feedback | `w_override = Uniform(alive)` | 同一 `_allocate_native`、同一拟合/支持/剪枝/χ² |

**明确不做：**

- 不改用于支持更新或剪枝的 `w_all`/`w_surv` 计算；  
- 不恢复已退出候选；  
- 不等于 Neutral 固定扫描，也不取消“拟合→支持→剪枝”递归。

## 实现位置

- 正式包 **未修改**：`pilot_fi_anchor/`  
- 消融包：`pilot_opp_feedback_ablation/`（外部调用 `Arm.step(..., w_override=...)`）

## RNG 配对（v0.2 修复）

| 版本 | Native alloc entropy | No-Opp alloc entropy | 问题 |
|---|---|---|---|
| v0.1 | `ARM_CODE[native]=0` | 独立 code=`2` | 权重效应与 RNG 流混淆 |
| **v0.2** | `ARM_CODE[native]=0` | **同一** `0`，独立 Generator 实例 | CRN：同权重同选点 |

正式 Native 复现：消融 Native 应与 `run_seed(..., do_perturb=False)` 的 Native 轨迹一致。
