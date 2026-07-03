# cktdetect 设计方案

**目标**：输入 SPICE netlist（HSPICE / ngspice / Spectre，可含 `.subckt` 层次，规模可达数百器件以上），输出电路类型判断及层次化结构标注。纯 rule-based（图算法 + 约束匹配 + 电路规则），不使用神经网络或 LLM。

**范围（v1 决策，2026-07）**：
- 覆盖领域：模拟基本块（OTA/比较器/偏置/bandgap/LDO）、射频（LNA/mixer/VCO）、无源网络（滤波器/匹配网络/分压器）。**不含**数字标准单元。
- 实现语言：Python（networkx 做图算法；性能瓶颈出现后再考虑重写热点）。
- 设计原则：**高 precision、允许 UNKNOWN**——宁可不识别，不可误识别。每个结论必须携带 evidence 列表。

---

## 1. 总体架构

```
SPICE netlist (hspice/ngspice/spectre)
        ↓
[0] Frontend Parser（分方言前端 → 统一 AST）
        ↓
[1] Design DB / Canonical IR（层次树 + 展平视图双表示）
        ↓
[2] Electrical Normalization + 全局网络分析
        （并联合并、S/D 对称化、电源/地/偏置网识别、DC domain 划分）
        ↓
[3] Primitive Motif Detection（声明式约束规则引擎 + 冲突消解）
        （mirror / diff pair / cascode / LC tank / 分压器 / 交叉耦合对 ...）
        ↓
[4] Iterative Graph Reduction（识别 → 压缩成 supernode → 再识别，至不动点）
        ↓
[5] Global Structure Analysis（反馈环检测、对称性检测、信号流方向推断）
        ↓
[6] Classification Layer（block 组合 + 全局证据 → 电路类型标签 + 置信度）
        ↓
[7] JSON 报告 / CLI / （后期）HTML viewer
```

前 5 层大体沿用 ChatGPT 讨论稿的骨架，但补齐了它缺失的四根承重柱：
**全局网络分析（2）、冲突消解（3）、全局结构分析（5）、顶层分类决策（6）**。

---

## 2. 各层设计要点

### [0] Parser 前端

- 每种方言一个薄前端（tokenizer + line parser），汇聚到同一个 AST。
- HSPICE 与 ngspice 语法接近，共享大部分实现；**Spectre 语法差异大，作为独立里程碑后置**（M5）。
- 只解析拓扑与关键参数（节点、model、W/L/M/value），对不认识的语法**容忍并告警跳过**，不追求完整 SPICE 兼容。
- 支持：续行、`.subckt/.ends`、`.param` 与简单表达式求值、`.include/.lib`（可选展开）、`.global`。
- 器件卡：M（MOS）、Q（BJT）、D、R、C、L、K（互感）、V/I 源、X（实例）。
- **Model 名 → 器件类型映射表可配置**（PDK profile）：默认内置常见规则（`nch*/nmos*/n_* → NMOS` 等正则），用户可提供 profile 文件覆盖。这是跨 PDK 的关键。

### [1] IR：层次树 + 展平视图双表示

- 层次树保留 `.subckt` 定义与实例化关系；展平视图给识别算法用，每个器件带 instance path。
- **层次是资产而不是负担**：
  - subckt 天然是大规模 netlist 的切分单元——先在每个 subckt 内部自底向上识别，结果沿实例复用（同一 subckt 多次实例化只识别一次）。
  - 这直接化解"数百器件以上"的规模问题：模式匹配几乎从不需要跨数百个 flat 器件，而是在每个 subckt 的几十个器件内进行，再向上组合。
  - subckt 名、端口名作为**低权重软证据**（名字会骗人，只加分、绝不作为 required 条件）。

### [2] 归一化 + 全局网络分析

归一化（同 ChatGPT 稿）：
- 并联同构 MOS 合并、M-factor/finger 归一、串联 stack 识别、R/C 串并联合并、S/D 端口规范化（对称器件不区分方向）。

**全局网络分析（新增，一切规则的前提）**：
- **电源/地识别**：net 名启发式（vdd/vss/gnd/avdd...）+ bulk 连接投票（绝大多数 PMOS bulk 指向的 net ≈ VDD）+ `.global` 声明 + DC 电压源连接。多证据加权，输出每个 net 的角色标签。
- **偏置网识别**：仅接 gate（高阻）且来源于 mirror/分压器的 net。
- **端口角色推断**：subckt 端口结合 V/I 源连接，推断 in / out / bias / supply。
- **DC domain 划分**：以耦合电容为割边，把 net 划分成 DC 连通域。这对 RF 电路尤其关键（AC 耦合到处都是），也用于 mirror 规则里的 `source_domain` 判断。

### [3] Primitive Motif Detection

声明式规则引擎，每个 pattern 定义：

```
Pattern DifferentialPair:
  Required:  两管同极性；共源节点；gate 不同 net；drain 不同 net
  Optional:  W/L 匹配 (+0.1)；drain 侧结构对称 (+0.1)；tail 接电流源 (+0.15)；gate 接输入端口 (+0.05)
  Forbidden: gate 短接
  base_score: 0.6
```

规则先用 Python dataclass/装饰器直接写（规则即代码，好调试），不急着发明 YAML DSL——等规则数超过几十条再抽象。

**v1 pattern 库**：

| 类别 | Patterns |
|---|---|
| MOS 模拟 | diode-connected、current mirror（simple/cascode/wide-swing/Wilson/多输出/scaled）、diff pair、cascode pair、source follower、common-source/common-gate 级、电流源/沉 |
| 无源 | 电阻分压器、RC/LC 梯形网络、串/并联谐振腔、T/Pi 网络、AC 耦合电容、去耦电容、偏置电阻 |
| 射频 | LC tank、源极电感退化、交叉耦合对（negative-gm）、变压器/互感耦合、匹配网络 |
| BJT | 镜像、ΔVbe 对（bandgap 核心） |

**冲突消解（ChatGPT 稿完全没提，实现中最大的坑）**：
一个器件常同时命中多个候选 motif（diode-connected 管既属于 mirror 又可判为 load）。策略：
1. 所有候选 match 带分数进入候选池；
2. 按"加权最大覆盖"选择互不冲突的 match 集合（贪心 + 优先级 tie-break，结果必须确定性）；
3. 落选候选保留为 alternative，供分类层在高层证据下翻案。

### [4] Iterative Graph Reduction

- 选定的 motif 压缩为 supernode（保留外部端口语义：`DIFF_PAIR.out_p/out_n/tail/in_p/in_n`）。
- 在压缩后的图上运行**第二层 pattern**（功能块级）：输入级、有源负载、尾偏置、输出级、偏置发生器、补偿网络、反馈网络、tank+负阻。
- 迭代至不动点。每一步压缩记录 provenance（supernode ↔ 原始器件集合），最终报告可逐层展开。

### [5] Global Structure Analysis（新增）

分类层需要的全局证据，motif 级看不到：
- **反馈环检测**：在信号流图上找环（去除电源/偏置 net 后），估计环路极性（沿环各级反相次数）→ 区分开环 OTA / 闭环放大 / LDO / 振荡器。
- **对称性检测**：WL（Weisfeiler–Lehman）图哈希 / 邻域签名找左右对称支路 → 差分结构、dummy 器件。ChatGPT 稿把签名放得很重，我们定位为**加速与对称检测的辅助手段**，不是主干。
- **信号流方向**：从输入端口经各增益级到输出端口的路径推断。

### [6] Classification Layer（"屋顶"，ChatGPT 稿缺失的最终目标）

规则将 block 组合 + 全局证据映射到电路类型：

| 证据组合 | 结论 |
|---|---|
| diff pair + mirror load + tail source，单级，无正反馈 | 单级 OTA |
| 上者 + 第二级 CS + Miller 电容 | 两级 OTA |
| OTA 结构 + 正反馈/再生 latch，无补偿 | 比较器 |
| 误差放大器 + 功率 pass 管 + 电阻分压反馈回输入 | LDO |
| ΔVbe BJT 对 + PTAT/CTAT 电流叠加 | bandgap |
| 交叉耦合对 + LC tank | LC VCO |
| CS/cascode 级 + 源极电感退化 + 输入匹配网络 | LNA |
| Gilbert cell 拓扑（双层开关四管 + 跨导对） | mixer |
| 输入/输出端口间纯 RC/LC 梯形，无有源器件 | 无源滤波器（阶数/类型由拓扑判定） |

- 输出**排序的候选标签 + 置信度 + evidence**；最高分低于阈值 → `UNKNOWN`。
- 大规模层次化输入：**逐 subckt 自底向上分类**，顶层输出组成清单（"本模块含：2× OTA、1× bandgap、1× LDO、1× 输出滤波器"）。

### [7] 输出

```json
{
  "top": "chip_top",
  "subckts": {
    "ota_core": {
      "classification": [
        {"type": "two_stage_ota", "confidence": 0.91,
         "evidence": ["diff_pair(M1,M2)", "mirror_load(M3,M4)",
                       "tail_source(M5)", "cs_second_stage(M6)",
                       "miller_cap(C1)"]}
      ],
      "structures": [
        {"type": "differential_pair", "devices": ["M1","M2"],
         "confidence": 0.95,
         "ports": {"in_p": "vip", "in_n": "vin", "tail": "ntail"}}
      ]
    }
  }
}
```

CLI：`cktdetect netlist.sp --dialect hspice --pdk-profile tsmc28.yaml -o report.json`

---

## 3. 对 ChatGPT 讨论稿的取舍总结

**采纳**：分层流水线；canonical IR 与归一化清单；Required/Optional/Forbidden 约束匹配；加权置信度；迭代 reduction；"宁 UNKNOWN 不误判"；MVP 先做 primitive recognizer。

**补齐**：
1. 顶层分类决策层（用户的真正目标是分类，稿子只建了地基）；
2. 电源/地/偏置网识别 pass（所有 mirror/pair 规则的前提）；
3. 无源器件与 BJT（Miller 电容、LDO 反馈电阻、bandgap 都靠它们）；
4. 反馈环 + 信号流分析（区分 OTA/LDO/振荡器的决定性证据）；
5. 冲突消解机制（重叠 match 的加权最大覆盖）；
6. DC domain 划分（RF 的 AC 耦合、mirror 的 source domain 判断都依赖）；
7. 层次化作为规模化策略（逐 subckt 识别 + 实例复用）；
8. 测试基准集先行。

**降权**：WL 签名从"特别建议"降为对称检测/加速的辅助手段；YAML pattern DSL 推迟到规则数量证明其必要。

---

## 4. 里程碑

| 里程碑 | 内容 | 验收标准 |
|---|---|---|
| **M0 基础设施** | HSPICE+ngspice parser、IR（层次+展平）、归一化、电源网识别、测试框架 + **20~30 个带标签的基准 netlist** | 基准集全部正确解析，电源/地识别准确 |
| **M1 模拟 primitive 识别器** | mirror/diff pair/cascode/diode-connected/电流源 + 置信度 + JSON 输出 | 教科书 OTA 电路的 primitive 全部正确识别，无误报 |
| **M2 Reduction + 模拟分类** | 图压缩、功能块、反馈环检测、OTA/比较器/两级 OTA 分类 | 基准集中放大器类电路正确分类 |
| **M3 无源 + 电源类** | R/C/L pattern、分压/滤波/去耦、BJT、LDO/bandgap/无源滤波器分类 | LDO、bandgap、RC 滤波器正确分类 |
| **M4 射频** | DC domain、LC tank、交叉耦合、电感退化、VCO/LNA/mixer 分类 | 典型 RF 教科书电路正确分类 |
| **M5 工程化** | Spectre 前端、大规模层次化优化、HTML/SVG viewer、netlist 结构 diff | 数百器件层次化 netlist 秒级出报告 |

**测试基准来源**：Razavi / Gray & Meyer 教科书电路手工转 netlist；ngspice 自带示例；SkyWater SKY130 开源 PDK 模拟块；OpenFASOC 生成电路。基准集与规则**同步增长**——每加一条规则，先加它的正例与反例。

---

## 5. 项目结构

```
cktdetect/
  parser/        # hspice.py  ngspice.py  spectre.py  ast.py  params.py
  ir/            # device.py  net.py  circuit.py  hierarchy.py
  passes/        # normalize.py  supply.py  dc_domain.py  ports.py
  patterns/      # base.py（规则引擎） analog.py  passive.py  rf.py  bjt.py
  reduce/        # reduction.py  cover.py（冲突消解）
  analysis/      # feedback.py  symmetry.py  signal_flow.py
  classify/      # rules.py  report.py
  cli.py
tests/
  benchmarks/    # 带标签基准 netlist：<name>.sp + <name>.expected.json
  unit/
```

**主要风险**：范围偏大（模拟+RF+无源 × 三方言）。缓解：里程碑严格串行，M1 结束即有一个可用、可演示的工具；RF 与 Spectre 都在主干验证之后。
