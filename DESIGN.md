# cktdetect 设计与规划文档

## 1. 目标与范围

**目标**：输入 SPICE netlist，自动判断电路类型，并给出结构标注（哪个管子是 tail、哪对管子是 mirror load……）。纯 rule-based（图算法 + 电路规则 + 角色标注），不使用神经网络或 LLM。

**范围（2026-07 决策）**：

| 维度 | v1 决定 |
|---|---|
| 电路领域 | 模拟基本块（OTA/比较器/偏置/bandgap/LDO）、射频（LNA/mixer/VCO）、无源网络（滤波器/匹配/分压）；**不含**数字标准单元 |
| netlist 语法 | 通用 SPICE 格式（标准 SPICE / ngspice / HSPICE 共同核心子集）；Spectre 及方言扩展后置 |
| 输入形态 | 支持 `.subckt` 层次；规模可达数百器件以上 |
| 实现语言 | Python |

**设计原则**：

1. **高 precision、允许 UNKNOWN**——宁可不识别，不可误识别。
2. **每个结论必须携带 evidence**——输出的不是黑盒标签，而是"因为 M5 的 gate 接在 diode 管 M6 的 bias 网上且位于栈底，所以它是 tail 电流源"这样可核查的证据链。
3. **每个电路类型独立交付**——新增一种类型 = 新增一个 verifier 函数 + 一组基准 netlist，不需要动核心引擎。
4. **基准集与规则同步增长**——每加一条规则，先加它的正例与反例。

---

## 2. 方法总览：branch-centric 识别

核心思路模仿模拟设计师读图的过程，而不是通用图模式匹配：

> 找到电源和地 → 顺着 VDD→VSS 数"腿"（DC 电流支路）→ 看每条腿里各管子的 gate 接到哪里，判断角色 → 看腿与腿之间怎么耦合 → 得出电路类型。

整个识别是**线性扫描 + 角色标注 + 小图分析**，避免了通用子图匹配的组合爆炸、motif 变体枚举和冲突消解问题。

```
SPICE netlist
    ↓
[P1] Parser（通用 SPICE 前端）
    ↓
[P2] IR：层次树 + 展平视图双表示
    ↓
[P3] 归一化（并联合并、M-factor、S/D 对称化）
    ↓
[P4] Net 角色标注：rail / bias / signal   ←—— mirror 在此免费浮现
    ↓
[P5] 支路分解：VDD→VSS 的 DC 电流腿        ←—— diff pair = 腿的分叉
    ↓
[P6] 器件角色标注：tail / cascode / diode / 放大管 / pass 管
    ↓
[P7] 腿级信号流图（节点=腿，边=耦合）      ←—— 规模在此坍缩为个位数节点
    ↓
[P8] 全局分析：级数、反馈环、对称性、补偿电容
    ↓
[P9] 假设驱动分类：全局特征提名候选类别 → 每类一个 verifier 核对
    ↓
[P10] JSON 报告（类型 + 置信度 + 角色标注 + evidence）
```

关键性质：

- **Current mirror 不需要模式匹配**：bias net 标注完成后，"驱动它的 diode 管 + 所有 gate 挂在它上面的管子"就是一个 mirror 家族，天然覆盖多输出、scaled、跨 subckt 变体。
- **差分对不需要模式匹配**：它是"一条腿在 tail 节点分叉"，分叉检测对 folded、complementary 变体一并适用。
- **不需要通用 graph reduction 引擎**：几百管的电路，腿级图通常只有几个到十几个节点，架构级分析直接在小图上做。
- **器件角色唯一**（由 gate 连接与栈内位置决定），不存在"一个器件同时命中多个 motif"的冲突消解问题。

---

## 3. 各阶段详细设计

### P1. Parser（通用 SPICE 前端）

- 覆盖标准 SPICE / ngspice / HSPICE 共同核心：器件卡 `M Q D R C L K V I E G X`，控制卡 `.subckt/.ends/.model/.param/.global/.end`；续行、行内注释、大小写不敏感。
- 只解析拓扑与关键参数（节点、model、W/L/M/value）；**不认识的语法容忍并告警跳过**，不追求完整 SPICE 兼容。
- `.model` 卡建立 model→器件类型表；无 `.model` 时用可配置的名字规则推断 MOS 极性（`nch*/nmos* → NMOS` 等），推断失败记 warning 并标为极性未知。
- 前端接口按多方言设计（每方言一个薄前端汇聚到同一 IR），Spectre 前端后置到 M5。

### P2. IR：层次树 + 展平视图

- 层次树保留 `.subckt` 定义与实例化；展平视图供识别用，器件/内部 net 带实例路径前缀。
- **层次是规模化策略**：先在每个 subckt 内部识别，同一 subckt 多次实例化只识别一次，结果沿实例复用；顶层输出组成清单（"本模块含 2× OTA、1× bandgap……"）。
- subckt 名、端口名只作**低权重软证据**（只加分，绝不作为 required 条件——名字会骗人）。

### P3. 归一化

- 并联同构 MOS 合并（含 M-factor / finger 归一）；
- R/C 串并联合并；
- MOS source/drain 对称化（对称器件不区分方向，匹配时按规范序）。

### P4. Net 角色标注

每个 net 标为 `rail`（power/ground）、`bias`、`signal`，迭代至不动点：

1. **rail**：net 名启发式（vdd/vss/gnd…，可配置）+ 节点 0 + DC 电压源参考 + bulk 连接投票（多证据、保守晋升）。
2. **bias**：被 diode-connected 器件驱动的 net；或仅扇出到 gate、由电流源支路保持的 net；或 DC 电压源驱动且只接 gate 的 net。
3. **signal**：其余；subckt 输入/输出端口给出方向提示。

副产品：每个 bias net 连同其 diode 驱动管与 gate 负载管，直接构成一个 **CurrentMirror 家族**记录（reference、outputs、比例来自 W/L 比）。

### P5. 支路分解（DC path decomposition）

- 从展平图中移除 rail 节点，器件间沿**导 DC 的端子**连通（MOS 的 S/D、R、L、BJT 的 C/E；**C 不导 DC，不入腿**，作为耦合边保留给 P7/P8）。
- 连通分量 = 一条腿（VDD→VSS 的器件栈）。栈内从上轨到下轨排序。
- **分叉检测**：腿内某 net 挂着 3 个及以上沟道端子（如 tail 节点分出两支）→ fork。差分结构 = 有 fork 的腿。
- AC 耦合电容把电路切成多个 **DC domain**（对 RF 关键），逐 domain 分解。

### P6. 器件角色标注

管子角色 = f(gate 所接 net 的角色, 在栈内的位置, 几何参数)：

| gate 接 | 栈内位置 | 角色 |
|---|---|---|
| 自己的 drain | — | diode |
| bias net | 栈底/栈顶（贴轨） | 电流源 / 电流沉（tail、load） |
| bias net | 串在放大管与轨之间 | cascode |
| signal net | — | 放大管 / 输入管 |
| signal net，且 W 显著大、drain/source 接输出端口 | 贴轨 | pass 管候选（LDO） |
| rail | — | 常开（等效电阻/dummy 候选） |

BJT 同理（base 对应 gate）。角色唯一、局部可判，线性扫描完成。

### P7. 腿级信号流图

- 节点 = 腿（附属性：是否分叉、栈签名、器件角色列表）。
- 有向边 = 耦合：A 腿中某器件的 drain 净驱动 B 腿中某器件的 gate（附增益极性估计：共源反相、follower 同相、共栅同相）；R/C 无源路径为另一类边（C 边标记为 AC 耦合）。
- 输入/输出端口挂到对应腿上。

### P8. 全局分析（在腿级小图上）

- **级数**：signal 从输入端口沿边到输出端口的最长增益路径跳数。
- **反馈环**：找环 + 沿环累计反相次数 → 负反馈（放大器/LDO/bandgap）或正反馈（latch/振荡器）。经电阻分压回到输入的环特别标记（LDO 特征）。
- **对称性**：栈签名相同、连接互为镜像的腿对 → 全差分结构、dummy 识别。
- **补偿/负载电容**：跨两级的 C → Miller 补偿；接输出到地的 C → 负载；串 R 的 Miller → nulling resistor。
- **正反馈 2-cycle**：两条腿互相驱动对方 gate → 交叉耦合核（VCO / latch）。

### P9. 假设驱动分类

两段式，像鉴别诊断：

1. **提名**：用便宜的全局特征向量剪枝候选类别（器件类型直方图、有无 L/BJT、端口数、腿数、级数、有无反馈环及极性、有无分叉腿、有无交叉耦合）。
2. **核对**：每个候选类别一个独立 **verifier 函数**，在腿级图上检查该类别的必要结构（Required）、累加可选证据（Optional）、检查排除条件（Forbidden），输出置信度 + 角色命名。

```
score = base(所有 Required 通过) + Σ w_i · Optional_i    （任一 Forbidden 命中 → 否决）
```

全部 verifier 未过阈值 → `UNKNOWN`（附最接近的候选与缺失的证据，方便人工复核）。

**置信度政策**（经全语料校准 harness 固化，见 `cktdetect/calibration.py`）：
阈值 0.6；规则结论上限 0.95，模板匹配 0.97；结论带 `scope` 层级
（system/block/template），跨层排序按层级、层内按置信度；每种类型的
实测置信度区间必须落在用户手册声明区间内（测试强制）。

### P10. 输出

```json
{
  "top": "chip_top",
  "subckts": {
    "ota_core": {
      "classification": [
        {"type": "two_stage_ota", "confidence": 0.92,
         "evidence": ["diff_branch(fork@ntail)", "mirror_load(M3,M4 on bias net n1)",
                       "tail_source(M5)", "second_gain_branch(M6,M7)",
                       "miller_cap(Cc bridges stage1→stage2)"]}
      ],
      "roles": {
        "M1": "input_pair", "M2": "input_pair", "M3": "mirror_load",
        "M4": "mirror_load", "M5": "tail_source", "M6": "cs_amplifier",
        "M7": "cs_current_sink", "Cc": "miller_compensation"
      },
      "branches": [...], "net_roles": {...}
    }
  },
  "composition": {"ota_core": 1, "bias_gen": 1},
  "warnings": []
}
```

CLI：`cktdetect netlist.sp [--top SUB] [--pdk-profile x.yaml] -o report.json`。后期加 HTML/SVG viewer 把腿和 block 框出来。

---

## 4. v1 电路类型 verifier 清单

| 类型 | Required（腿级判据） | 典型 Optional 证据 |
|---|---|---|
| 电流镜偏置网络 | ≥1 个 bias net 家族（diode + 负载管） | W/L 成整数比；专用偏置腿 |
| 单级 OTA（5T） | 分叉差分腿 + mirror load + tail 电流源，1 级，无反馈环 | 输入对几何匹配；负载电容 |
| 两级 OTA | 上者 + 第二增益腿 | 跨级 Miller 电容（强证据）；nulling R |
| folded cascode OTA | 分叉腿的 drain 折入**反极性** cascode | 宽摆幅偏置 |
| telescopic OTA | 分叉腿的输出上直接叠**同极性** cascode | 镜像负载在 cascode 输出 |
| 全差分 OTA | 差分对 + 双输出均为电流源负载（无镜像、无 cascode 接管、无交叉耦合） | 电阻共模反馈（双输出经 R 汇到一个 net 并驱动某管栅极）；负载几何匹配 |
| 比较器（静态 latch） | OTA 型前级 + 正反馈 2-cycle 直接落在对管输出上 | 时钟/复位开关管 |
| StrongARM 动态比较器 | 时钟 net 同时驱动"源接地 NMOS 尾管 + ≥2 个源接电源 PMOS 预充管" + 输入对 + 再生交叉耦合 | 互补双交叉耦合对 |
| beta-multiplier 偏置 | 镜像与反极性 diode 互锁 + 伴管把环路闭回镜像栅网 + 源极退化电阻 | 伴管/diode 的 W/L 比 > 1 |
| source follower / buffer | 单腿，gate 输入、source 输出 | 电平移位用途证据 |
| LDO | 误差放大器（复用 OTA verifier）+ pass 管 + 经电阻分压的负反馈环 | 输出大电容；使能管 |
| bandgap | BJT/diode ΔVbe 对 + mirror 强制电流比 + 负反馈 | PTAT 电阻；启动电路 |
| LC VCO | 交叉耦合腿对（正反馈 2-cycle）+ LC tank + tail | varactor；输出 buffer |
| LNA | cascode 腿 + 源极电感退化 + 输入 L/C 匹配网络 | 输出 tank；偏置去耦 |
| Gilbert mixer | 三层栈：跨导对之上再分叉出开关四管 | LO/RF/IF 端口区分 |
| 共源放大器 | 单个 common_source 角色增益管（排除反相器/推挽成员），无差分对 | 电流源/电阻/电容负载 |
| rail-to-rail 输入级 | 两个**互补极性**差分对共享同一对输入 net | 两侧独立尾电流源 |
| class-AB 输出级 | 互补 common_source 对共享输出 drain，**栅驱动 net 不同**（相同=数字反相器，排除） | 输出负载 |
| 环形振荡器 | 反相器 input→output 关系上的**奇数长度环**（≥3 级） | 纯环（无对/镜像） |
| 采样保持 | 时钟控 pass 管 + 高阻保持节点（仅此一个沟道连接）+ 对地保持电容 | 保持节点后接 follower 缓冲 |
| Dickson 电荷泵 | ≥3 个 diode 接法器件串联链 + ≥2 个内部节点挂非轨"泵电容" | ≥2 个交替时钟 net |
| R-2R 梯形网络 | 无源；串联 R 骨架链（≥3 节点）+ 每个骨架节点一条 2R 支路（5% 容差） | 2R 对地端接 |
| PLL（系统级） | 块实例图：振荡器块 + 控制块 + 环路滤波块经三段互不相同的共享网闭环 | 外部参考输入 |
| flash ADC（系统级） | 块实例图：≥3 比较器实例 + 电阻梯抽头一一对应 + 共享输入网 | 每比较器独立抽头 |
| VCO 开环级链（系统级） | ≥3 个同 subckt 反相级实例连成简单开链 + 全体共享非轨控制网 + 链端开放 | —（闭链交给平坦环规则） |
| 无源滤波器 | 端口间纯 R/C/L 梯形，无有源器件（走独立的梯形分析器，见下） | 阶数/类型（低通/高通/带通）判定 |

**无源网络分析器**（独立路径）：没有 DC 腿的纯无源电路，用端口间的串并联/梯形拓扑归约判定分压器、RC/LC 滤波器、T/Pi 匹配网络及其阶数。

**模板库**（后期补充）：带标签的参考 netlist 经归一化后做图同构比对，作为已知精确拓扑的快速通道；添加新模板不需要写代码。

---

## 5. 边界与已知不适用场景

- **switched-cap 电路**：DC 路径被开关切断，腿分解失效 → v1 明确输出 UNKNOWN（附"检测到开关+电容阵列"提示）。
- **translinear / 电流模复杂环路**：v1 不做。
- **大量 pass-gate 的模拟开关阵列**：腿的边界模糊，弱项，宁可 UNKNOWN。
- **数字标准单元**：范围外；遇到明显的互补推挽结构提示"疑似数字逻辑"。
- MOS 极性无法推断（无 `.model`、名字不规范）时降级：只输出拓扑级结构，不做需要极性的判断。

---

## 6. 测试策略

- **基准集**：`tests/benchmarks/<name>.sp` + `<name>.expected.json`，来源：Razavi / Gray & Meyer 教科书电路手工转写、ngspice 示例、SKY130 开源 PDK 模拟块、OpenFASOC 生成电路。目标 v1 结束 ≥ 40 个。
- **外部验证集**：`tests/external/`（独立第三方 netlist，防止规则自我印证）。首批为 ALIGN benchmark 12 个电路（BSD-3-Clause），结果与已知缺口记录在 `tests/external/README.md`。
- **每个 verifier 必须带**：≥2 个正例、≥2 个近似反例（如"共源共栅放大器不是 OTA"、"两个共源管不是差分对"）。
- **单元测试**：parser（语法容忍、续行、.param、.model）、展平（层次、递归检测）、net 角色、腿分解（分叉、DC domain）。
- **回归原则**：任何误识别修复都先固化为反例基准。

---

## 7. 里程碑

| 里程碑 | 内容 | 验收标准 |
|---|---|---|
| **M0 基础设施** | 通用 SPICE parser、IR（层次+展平）、归一化、rail 识别、测试框架 + 首批基准 netlist | 基准集全部正确解析；rail 识别准确 |
| **M1 角色与支路** | net 角色标注（bias/signal + mirror 家族）、支路分解（分叉、DC domain）、器件角色标注；结构级 JSON 报告 | 教科书 OTA 电路的 mirror/diff pair/tail/cascode 全部正确标注，零误报 |
| **M2 腿级图与放大器分类** | 腿级信号流图、级数/反馈/对称/补偿分析、verifier：单级 OTA、两级 OTA、folded cascode、比较器、buffer、镜像偏置 | 基准集中放大器类电路正确分类，UNKNOWN 行为正确 |
| **M3 电源与无源** | 无源梯形分析器、BJT 支持完善、verifier：LDO、bandgap、无源滤波器/分压器 | 对应基准电路正确分类 |
| **M4 射频** | DC domain 完善、LC tank / 交叉耦合 / 电感退化检测、verifier：LC VCO、LNA、Gilbert mixer | 典型 RF 教科书电路正确分类 |
| **M5 工程化** | Spectre 前端、模板库、HTML/SVG viewer、层次化大规模优化、netlist 结构 diff | 数百器件层次化 netlist 秒级出报告 |

---

## 8. 项目结构

```
cktdetect/
  parser/        # spice.py（通用 SPICE 前端） values.py（数值/表达式）
  ir/            # device.py  circuit.py  flatten.py
  passes/        # normalize.py  rails.py  netroles.py  branches.py  devroles.py
  graph/         # stagegraph.py  feedback.py  symmetry.py
  classify/      # features.py  verifiers/（每类型一个文件） report.py
  passive/       # ladder.py（无源网络分析器）
  cli.py
tests/
  benchmarks/    # <name>.sp + <name>.expected.json
  unit/
```

---

## 附录：方法选型记录

曾考虑的方案是"通用 motif 子图匹配 + 迭代 graph reduction"（bottom-up：识别小 motif → 压缩成 supernode → 再识别，至不动点）。放弃其作为主干的原因：

1. mirror/cascode/diode 等在角色标注表示下是**线性扫描的副产品**，无需为每种变体写 pattern，也没有"一个器件命中多个 motif"的冲突消解问题；
2. 差分对的本质是"腿的分叉"，比"两管共源"的子图模式对 folded/complementary 变体更鲁棒；
3. 通用 reduction 引擎是整个方案中实现风险最高的组件，而腿级图天然只有个位数节点，架构级分析不需要它；
4. top-down 假设驱动分类让每个电路类型成为独立可交付的 verifier，避免"必须先建成完整通用引擎才能出第一个结果"。

保留自该方案的元素：Required/Optional/Forbidden 约束式 verifier 与加权置信度；模板库作为后期补充；parser/IR/归一化/rail 识别等基础层两种方案通用。
