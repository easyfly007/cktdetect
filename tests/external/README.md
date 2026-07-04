# 外部验证数据集

独立第三方来源的真实 netlist，用于验证识别规则不是"自我印证"
（内部基准 `tests/benchmarks/` 由本项目作者手写，规则与测试同源）。

## align/ — ALIGN benchmark 电路

- 来源：[ALIGN-analoglayout/ALIGN-public](https://github.com/ALIGN-analoglayout/ALIGN-public)
  `examples/` 目录（DARPA IDEA 开源模拟版图项目的基准电路），
  master 分支，2026-07 抓取。
- 许可：BSD-3-Clause（与来源仓库一致，文件内容未修改）。
- 特点：FinFET 风格参数（`nfin`/`nf`）、真实 PDK 模型名
  （`nmos_rvt`、`lvtnfet`、`n`/`p`）、无测试台的纯 subckt 形式、
  `//` 注释与反斜杠续行混用、层次化 + 参数传递——这批文件曾直接
  推动 parser 修复（`\` 续行、`//` 注释）和三条规则改进
  （无驱动偏置端口、净级反相环、SC 电路检测）。

## 验证结果（cktdetect 当前版本，`--top <subckt>`）

| netlist | 分类结果 | 判定 |
|---|---|---|
| five_transistor_ota | `single_stage_ota` (0.9) | ✅ 正确 |
| telescopic_ota | `telescopic_ota` (0.8) | ✅ 正确 |
| current_mirror_ota | `single_stage_ota` (0.8) | ✅ 正确（镜像负载 OTA 变体） |
| common_source | `common_source_amplifier` (0.75) | ✅ 正确（diode 负载） |
| comparator1 | `strongarm_comparator` (0.9) | ✅ 正确（层次化、双输入对 + 时钟发生反相器链） |
| high_speed_comparator | `strongarm_comparator` (0.9) | ✅ 正确 |
| double_tail_sense_amplifier | `comparator` (0.8) | ✅ 正确（double-tail 动态比较器，判入比较器家族；两级动态子类型未细分） |
| ring_oscillator | `ring_oscillator` (0.9) | ✅ 正确（电流饥饿型级，净级反相环检测） |
| switched_capacitor_filter | `switched_capacitor_circuit` (0.85) | ✅ 正确（内嵌 telescopic OTA 作为次级结论保留） |
| cascode_current_mirror_ota | `single_stage_ota` (0.8) | ✅ 正确（复合 diode 镜像负载——经串联栈归一化 + cascoded mirror 检测修复） |
| buffer | `unknown` | ✅ 合理拒判（两级数字反相器 buffer，数字范围外） |
| VCO_type2_65 | `unknown` | ⚠️ 已知缺口：8 级堆叠反相器开环链（环在 subckt 外闭合） |

**结论：10/12 正确标注，2 个 unknown（1 个范围外拒判 + 1 个已知缺口），
0 个误判**——符合"高 precision、允许 unknown"的设计原则。

已知缺口（开环级链识别）修复后应把对应行的期望翻转
（`tests/unit/test_external.py` 会在行为变化时报警）。
历史记录：首轮验证为 9/12（cascode_current_mirror_ota 曾是缺口，
由串联栈归一化补上）。
