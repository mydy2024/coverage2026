# DDR5 Vref coverage v1

这是首个面向真实 testbench 接入的独立 SV 垂直切片，覆盖 JESD79-5D
Table 125/127 中 VrefCA/VrefCS 到后续合法命令的延迟关系。

## 文件

- `ddr5_vref_cov_pkg.sv`：命令和结果类型。
- `ddr5_vref_cov_if.sv`：coverage collector、历史状态、计数器和 covergroups。
- `ddr5_vref_adapter_template.sv`：暂定 monitor 事件接口。
- `ddr5_vref_smoke_tb.sv`：边界、违例、跨 rank 和 epoch 清除测试。
- `ddr5_vref_rules.json`：范围、规范位置和 adapter 契约。
- `source_map.json`：规则到covergroup、coverpoint和违例计数器的映射。
- `ddr5_vref.f` / `ddr5_vref_smoke.f`：集成与 smoke filelist。

## 暂定接口

真实 monitor 每产生一个已经解码、不可变的语义命令事件，就调用：

```systemverilog
coverage.observe(timestamp_fs,
                 channel, subchannel, rank,
                 config_epoch, reset_epoch,
                 tck_fs,
                 is_reset, command_valid, command);
```

时间统一使用整数 femtosecond。调用在同一个 scope 内必须严格按时间递增。
`command_valid=false` 表示观测不可信，会保守清除该 scope 的 Vref 历史。

多周期 Vref 命令的原始边沿合并、1N/2N 采样和 Table 125/127 起止锚点由
adapter 负责。collector 只消费已经归一化的语义事件，因此接入不同 TB 时不需要
修改 covergroup 或状态逻辑。

## tMRD

当前规则使用现有 DDR5 资产中的定义：

```text
tMRD = max(14 ns, 16*tCK)
```

阈值在 Vref start 事件处保存。如果 tCK 发生变化，adapter 必须先增加
`config_epoch`；否则 collector 会报错。

## 覆盖模型

VrefCA 和 VrefCS 各有一个 covergroup：

- end command coverpoint：19 个 Table 125/127 目标命令；
- outcome coverpoint：`at_bound`、`above_bound`；`below_bound` 从合法覆盖中忽略；
- end command × outcome cross：共 38 个合法关系目标。

合法覆盖与违例计数严格分开，违例不会提高覆盖率。无历史、reset/epoch 清除后的
事件不会形成伪间隔。

## 仿真命令模板

静态前端检查：

```bash
python tools/check_ddr5_vref_sv.py
```

在支持 covergroup 的商业仿真器中，从本目录执行，例如：

```text
vcs -sverilog -f ddr5_vref_smoke.f -top ddr5_vref_smoke_tb
xrun -sv -f ddr5_vref_smoke.f -top ddr5_vref_smoke_tb
vlog -sv -f ddr5_vref_smoke.f
```

具体 coverage 开关和运行命令以真实工程为准。本目录暂不声明已经在商业仿真器
运行；静态前端检查和真实仿真结果分别记录。

## 后续 TB 接入

完整的环境登记、基线运行、adapter绑定、边界测试、coverage导出和M0/M1验收步骤见
[获得仿真环境后的接入执行手册](../../docs/09_获得仿真环境后的接入执行手册.md)。

拿到真实 monitor 后只替换 `ddr5_vref_adapter_template.sv`，需要确认：

1. monitor 命令枚举到 `ddr5_vref_cmd_e` 的映射；
2. Vref 多周期命令的规范测量锚点；
3. channel/subchannel/rank 来源；
4. MR 或速度变化对应的 `config_epoch`；
5. reset 展开到各 scope 的策略；
6. 原生 coverage 导出路径和 checker 结果。

当前状态是“独立交付包、真实 TB binding 待接入”，不是 coverage closure。
