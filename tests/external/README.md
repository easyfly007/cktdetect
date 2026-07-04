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
| VCO_type2_65 | `vco_stage_chain` (0.8) | ✅ 正确（8 级压控反相级开环链，环在 subckt 外闭合——块组合级识别） |
| buffer | `unknown` | ✅ 合理拒判（两级数字反相器 buffer，数字范围外） |

**结论：11/12 正确标注，1 个合理拒判，0 个误判**——符合
"高 precision、允许 unknown"的设计原则。

历史记录：首轮验证为 9/12；cascode_current_mirror_ota 缺口由串联栈
归一化补上，VCO_type2_65 缺口由开环级链（vco_stage_chain）识别补上。
`tests/unit/test_external.py` 固化全部期望，行为变化时报警。

## openfasoc/ — OpenFASOC 生成器电路（SKY130）

- 来源：[idea-fasoc/OpenFASOC](https://github.com/idea-fasoc/OpenFASOC)
  （开源硅生成器项目，SKY130 流片过），main 分支，2026-07 抓取。
- 许可：Apache-2.0（与来源仓库一致，文件内容未修改）。
- 特点：**SKY130 惯例——器件以 X 卡实例化 PDK 原语**
  （`X0 d g s b sky130_fd_pr__nfet_01v8 w=.. l=..`），必须配
  `profiles/sky130.json` PDK profile（X 实例提升 + vpwr/vgnd 轨名）；
  xschem 导出风格（带空格的引号参数表达式、`sw<7>` 总线名、
  `**` 注释）。这批文件直接推动了 X 实例提升机制、引号参数空格
  处理，以及三处平方级热点的性能修复（20136 器件 48s → 1.3s）。

## 验证结果（`--pdk-profile profiles/sky130.json --top <subckt>`）

| netlist | 电路 | 分类结果 | 判定 |
|---|---|---|---|
| DCDC_COMP.sp | PMU 时钟比较器 | `strongarm_comparator` (0.9) | ✅ 正确 |
| LC_Cell.spice | LC-DCO 谐振单元 | `lc_vco` (0.8) | ✅ 正确（电容在开关电容 bank，inductor-only tank 判据） |
| swcap_3M2C.spice | DCO 开关电容 bank（534 器件） | `switched_capacitor_circuit` (0.85) | ✅ 正确 |
| six_stage_conv.sp | 六级 SC DC-DC 变换器（20136 器件） | `switched_capacitor_circuit` (0.85) | ✅ 正确，1.3 秒完成 |
| diff_cross_mirror.spice | DCO 负阻辅助单元 | `unknown` | ✅ 合理拒判（tank 在上层 LC cell，单独的交叉耦合+镜像不足以定型；交叉耦合结构在报告中可见） |

**结论：4/5 正确标注 + 1 个合理拒判，0 个误判。**

## 两个数据集合计

17 个第三方电路：**15 个正确标注、2 个合理拒判、0 个误判、
0 个遗留缺口**。
