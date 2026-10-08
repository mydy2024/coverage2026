# O1: 独立离线基准实验包

本目录是 [07 无工程环境的离线路线](../../docs/07_无工程环境的离线路线.md) 中 O1 的实现。

## 目的

在不依赖 DUT、仿真器或工程环境的前提下，验证框架的规则表达、历史状态管理、采样分类和证据追溯能力。每个场景的预期结果由人工推导并独立存档，不调用被测重放器生成。

## 关键约束

- **预期不调用重放器**：`cases.json` 中的 `expected` 字段是人工根据 `spec.md` 语义推导的，不是运行 replay 后回填的。
- **逐项对照**：harness 对每个 sample 的 `outcome`、`interval_ticks`、`bin_id`、`suppression_reason`、`start_event_id` 以及 summary 聚合指标逐字段比较。
- **不冒充 DDR5**：所有协议是教学性质的离线基准，不代表 JEDEC 规格。

## 文件说明

| 文件 | 作用 |
|---|---|
| `spec.md` | 离线基准协议规格（单规则、双规则、自重叠三节） |
| `create_baselines.py` | 从 spec.md 哈希生成 3 个 plan 文件 |
| `plans/single_rule.json` | START→END, bound=4 |
| `plans/dual_rule.json` | 规则A: START→END bound=4; 规则B: END→DONE bound=5 |
| `plans/self_overlap.json` | START 既是 start 又是 end, bound=4 |
| `cases.json` | 13 个场景定义 + 人工预期结果 + 推导理由 |
| `harness.py` | 比较器：运行 replay，逐项对照人工预期 |

## 场景清单

| # | 名称 | 覆盖能力 |
|---|---|---|
| 01 | at_bound | 边界命中 |
| 02 | above_bound | 超出边界命中 |
| 03 | below_bound_violation | 违例不计入合法覆盖 |
| 04 | no_history | 无起始历史时抑制 |
| 05 | latest_start_wins | latest_start 策略 |
| 06 | reset_clears_history | **复位清除历史** |
| 07 | cross_rank_independent | **跨 rank scope 隔离** |
| 08 | config_epoch_change | **config_epoch 变化清除历史** |
| 09 | reset_epoch_change | **reset_epoch 变化清除历史** |
| 10 | invalid_event_clears | **无效事件抑制并清除历史** |
| 11 | duplicate_idempotent | 精确重复幂等 |
| 12 | self_overlap | 命令既是 start 又是 end（measure-before-update） |
| 13 | multi_rule_shared | **多规则共享事件**（END 是规则A的end和规则B的start） |

加粗项对应 07 文档 O1 要求的场景。

## 运行方式

```powershell
# 1. 生成 plan 文件（仅首次或 spec.md 变更后需要）
python experiments/offline_baseline/create_baselines.py

# 2. 运行全部场景
python experiments/offline_baseline/harness.py

# 3. 查看逐字段差异
python experiments/offline_baseline/harness.py --verbose

# 4. 只运行单个场景
python experiments/offline_baseline/harness.py --case 10_invalid_event_clears
```

退出码：0=全部通过，1=有失败。

## 既有测试的关系

本实验包与 `tests/test_replay.py` 的 27 个单元测试互补：
- 单元测试在函数级别断言特定属性（如"违例不增加合法覆盖"）。
- 本实验包在场景级别存档完整的人工预期（每个 sample 的每个语义字段），并逐项对照。
- 两者都不声称已验证真实 DDR5 行为。

## 不做的事情

- 不生成 DDR5 仿真结果。
- 不证明 Python 重放与 SV collector 动态等价。
- 不计算原生 coverage 数据库计数。
- `closure_claim` 始终为 false。
