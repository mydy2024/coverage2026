# CoverageClosure：可追溯、可验证的 DDR5 覆盖闭环

设计基线：2026-10-08，v0.1。状态：**已实现事件重放、SV collector生成和证据追溯原型；尚未接入真实 DDR5 仿真，M0/M1 尚未验收**。

本方案按你的选择设计：DDR5 小子集起步，复用已有商业仿真器和 DDR5 DUT/testbench，同时为工程应用与论文实验保留证据。建议将系统中心从“四个阶段的置信度传播”调整为“带版本的验证义务与证据链”，先做到每个结论可定位、可重放、可推翻，再研究诊断策略优化。

**当前执行路线：离线优先。** 用户暂时无法提供工程环境信息，近期按[无工程环境的离线路线](docs/07_无工程环境的离线路线.md)推进独立基准、采样语义、诊断与修复回归。真实DDR5接入单独待验收，不再作为离线开发前置条件。

## 阅读入口

| 文档 | 解决的问题 |
|---|---|
| [01 现状审计](docs/01_现状审计.md) | 当前代码哪里有问题、哪些结论已复现、哪些模块保留 |
| [02 总体方案](docs/02_总体方案.md) | 架构、三层 IR、证据图、诊断与修复、真正的闭环条件 |
| [03 数据契约与 DDR5 示例](docs/03_数据契约与DDR5示例.md) | 对象字段、稳定 ID、采样语义、首批 DDR5 目标、仿真接口 |
| [04 实施计划](docs/04_实施计划.md) | 8 周里程碑、前 10 个工作日、依赖与验收门槛 |
| [05 论文实验设计](docs/05_论文实验设计.md) | 基线、故障注入、指标、消融、可主张的贡献边界 |
| [06 首版实现与接入](docs/06_首版实现与接入.md) | 已实现能力、运行命令、复用monitor的事件契约、当前限制 |
| [07 无工程环境的离线路线](docs/07_无工程环境的离线路线.md) | 当前优先工作、独立基准、离线诊断与工程验收边界 |
| [08 离线基准O1交付与当前进展](docs/08_离线基准O1交付与当前进展.md) | O1 交付物、13 个场景验证结果、当前项目状态 |
| [材料核对笔记](reference_notes/材料核对.md) | PPT、ChatFCM、JEDEC 对方案的支持与需要修正之处 |

## 一条完整的链

```text
规格文件及页内位置 → 原子要求 → Atomic/Derived/Relation IR
  → 验证义务和 bin → 生成代码及 source map → 真实运行与事件
  → 未命中/异常 → 诊断假设及区分实验 → 修复版本
  → 同场景重放和回归 → 有证据的关闭，或保留未解决状态
```

这条链必须双向查询：从某个 bin 回到原文和运行证据；从某条规格变更找出受影响 IR、代码、bins 和需要重跑的测试。KG 是这条依赖链的查询视图；可执行语义放在类型明确的 IR 中。

## 已确定的决策

- 首批围绕已有 VrefCA/VrefCS 资产，分两批引入命令识别、命令间隔、CS 持续时间与 setup/hold，共约 10 条候选规则；经原文和环境核对后冻结清单。
- 前期复用已有 monitor、driver、checker，新增旁路观测和 coverage collector。原始 pin 证据仍要保留，已有 monitor 也需要对拍。
- 不默认生成新的SV interface或DDR5指令decoder；缺少什么观测能力，才补相应adapter/探针。首版生成器接收解码事件，仅生成派生测量与covergroup。
- LLM 用于规格提取、解释歧义和提出激励/修复候选；类型检查、代码生成、计分、关闭状态转换采用确定性规则。
- 区分来源完整度、模型正确性、运行覆盖率、checker 检测能力；不混成一个“正确概率”。
- 无进展、超时、预算耗尽都保留 unresolved；不可达需要与配置、模型和版本绑定的证明。
- 不直接沿用 PPT 中“剩余 uncover 归 D”的规则，不把 ChatFCM 的功能正确率当成运行覆盖率。

## 第一版代码：可以立即运行

在本目录执行，Python 3.11+，核心功能无需第三方依赖：

```powershell
python cc.py validate --plan examples/min_interval/plan.json
python cc.py replay --plan examples/min_interval/plan.json --run examples/min_interval/directed.run.json --events examples/min_interval/directed.events.jsonl --out runs/my-first-replay
python cc.py trace-bin --report runs/my-first-replay/report.json --bin rel.fixture.interval.at_bound
python -m unittest discover -s tests -v
```

输出目录必须不存在。示例是明确标注的教学协议，不是DDR5仿真结果；它演示事件→区间测量→bin→原文/代码/事件追溯。`closure_claim`始终为false，原生coverage、独立checker及真实环境验证尚未接入。[详细用法与接入边界](docs/06_首版实现与接入.md)

`examples/ddr5_vref/plan.draft.json`保留真实规范来源哈希，并对tMRD、测量锚点、目标范围和monitor binding缺失明确报blocked，不会猜测阈值生成模型。

## 规划阶段交付与核查范围

已读取 21 页 PPT 文本、9 页论文文本并重点核查第 4–7 页，检索 534 页 JEDEC PDF并查看相关命令表、Vref 时序条文及图表。对旧脚本进行了只读探测和内存生成对比，结果见 [legacy_audit.json](reference_notes/legacy_audit.json)。源文件 SHA-256 见 [source_manifest.json](reference_notes/source_manifest.json)。

旧工程源代码、KG 与生成产物未修改。未运行旧工程完整流水线，未执行商业仿真或宣称新系统已闭环。本会话的 Windows PATH 未发现常用仿真器命令；这不否定你已有其他主机或环境上的仿真资源。后续实现的检查与演示结果见 `reference_notes/implementation_checks.json`。

`reference_notes/extracted/` 是本地阅读缓存；`reference_notes/figures/` 是页图；`.tools/python/` 包含PDF读取依赖与可选SV前端检查工具。需要重新抽取时运行 `python tools/extract_references.py`，依赖PyMuPDF 1.28.2；SV检查使用 `python tools/check_generated_sv.py`，依赖pyslang 12.0.0。

当前下一步是建立独立离线基准与受控故障实验包。O1（独立离线基准，13 个场景）已交付并通过验证，见[08 离线基准O1交付与当前进展](docs/08_离线基准O1交付与当前进展.md)；下一项是 O3（证据驱动诊断）的最小案例。`configs/environment.json`可以保持未配置；其doctor结果仅表示真实环境尚未接入，不阻止离线工作。环境可用后再完成M0/M1真实事务证据链验收。
