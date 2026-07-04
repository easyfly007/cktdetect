# cktdetect 用户手册

cktdetect 读入一个 SPICE / Spectre netlist，自动判断电路类型，并标注每个
器件的角色（哪个管子是尾电流源、哪对管子是电流镜……）。纯规则实现，不使用
神经网络或 LLM；每个结论都携带置信度和可核查的证据链，认不出时明确输出
`unknown`，绝不猜测。

---

## 1. 安装

需要 Python ≥ 3.10，无第三方运行时依赖。

```console
git clone https://github.com/easyfly007/cktdetect.git
cd cktdetect
python3 -m venv .venv
.venv/bin/pip install -e .
```

安装后 `.venv/bin/cktdetect` 可用；开发者另装 pytest 跑测试：
`.venv/bin/pip install pytest && .venv/bin/python -m pytest`。

## 2. 快速开始

```console
$ cktdetect tests/benchmarks/five_t_ota.sp
```

输出 JSON 报告（节选）：

```json
{
  "classification": [
    {
      "type": "single_stage_ota",
      "confidence": 0.9,
      "evidence": [
        "differential pair xota.m1,xota.m2 (tail net 'xota.tail')",
        "current-mirror load (reference xota.m3)",
        "tail current source xota.m5",
        "mirror covers both pair outputs"
      ]
    }
  ],
  "device_roles": {
    "xota.m1": {"role": "diff_input", "evidence": ["..."]},
    "xota.m5": {"role": "tail_current_source", "evidence": ["..."]}
  }
}
```

## 3. 命令行参考

```
cktdetect NETLIST [选项]
```

| 选项 | 说明 |
|---|---|
| `--top SUBCKT` | 只分析指定 subckt（以其定义为顶层展平），而不是顶层器件 |
| `--dialect auto\|spice\|spectre` | netlist 方言，默认 `auto` 自动检测 |
| `--templates DIR` | 模板库目录，匹配到的模板作为最高优先级结论（见第 8 章） |
| `--pdk-profile FILE` | PDK profile（JSON）：模型名 → 器件类型映射、电源/地网名模式（见 4.3） |
| `--html FILE` | 额外生成自包含的 HTML 可视化报告（见第 9 章） |
| `--diff OTHER` | 与另一个 netlist 做结构级对比，输出 diff（见第 10 章） |
| `-o FILE` | JSON 报告写入文件（默认打印到 stdout） |

## 4. 输入格式

### 4.1 SPICE 方言

支持标准 SPICE / ngspice / HSPICE 的共同核心子集：

- 器件卡：`M`（MOS）、`Q`（BJT）、`D`、`R`、`C`、`L`、`K`（互感）、
  `V`、`I`、`E`/`G`（受控源）、`X`（subckt 实例）；
- 控制卡：`.subckt/.ends`、`.model`、`.param`（含简单算术表达式）、
  `.global`、`.end`；
- `+` 续行、`*` 注释行、`$`/`;` 行内注释、大小写不敏感、
  SI 数值后缀（`2u`、`10meg`、`1.5e-9`）。

**容错原则**：不认识的语法（未知器件卡、未知控制卡）告警跳过，不会让
解析失败；所有告警收集在报告的 `warnings` 字段。

**标题行**：按标准 SPICE 约定，文件第一行若不能解析为语句则视为标题。

**`.include` / `.lib` 自动展开**：`.include file`（相对被包含文件所在
目录解析，支持引号路径、嵌套）；`.lib 'file' section` 只引入库文件中
对应 `.lib section … .endl` 段。循环包含和超深嵌套（>16 层）会告警
跳过而不是死循环。文件不存在只告警，解析继续。

**CDL 格式**：工业界常见的 CDL 导出可直接解析（走 SPICE 前端，`.cdl`
扩展名自动识别）：`X… / subckt` 的斜杠分隔符、`$X=… $PINS` 等行内
属性（自动剥除）、`*.PININFO` 等注释卡都能处理。

**subckt 参数**：支持 `.subckt name a b W=2u` 默认参数、
`X1 n1 n2 sub W=4u` 实例覆盖、subckt 作用域内的 `.param`（可引用
subckt 参数写表达式），在展平时按"全局 → subckt 默认/局部 → 实例
覆盖"的层级求值；实例上的 `m=` 会沿层次连乘到内部所有器件。

### 4.2 Spectre 方言

支持 `subckt/ends`、`model`（经 `type=n/p/npn/pnp` 解析极性）、
`parameters`、`global`、括号形式的实例行
`M1 (d g s b) nch w=4u l=0.5u`（无括号形式也接受）。
未知 master 按 subckt 实例处理。

**方言自动检测**：文件含 `simulator lang=spectre` 或扩展名为 `.scs`
→ Spectre；否则按 SPICE 解析。可用 `--dialect` 强制指定。

### 4.3 MOS/BJT 极性推断

优先级：**PDK profile**（若提供）→ `.model` 卡（`nmos/pmos/npn/pnp`）
→ 模型名推断（`nch*/nmos*/nfet*/n* → NMOS`，`pch*/pmos*/pfet*/p* →
PMOS`）。全部失败时该管标为"极性未知"并告警——依赖极性的判断会降级。

**PDK profile**（`--pdk-profile prof.json`）用于模型名不规范、又没有
`.model` 卡的 PDK：

```json
{
  "models":      {"sky130_fd_pr__nfet*": "nmos",
                  "sky130_fd_pr__pfet*": "pmos",
                  "my_vert_pnp": "pnp"},
  "power_nets":  ["vpwr*"],
  "ground_nets": ["vgnd*"]
}
```

模型名支持 glob 通配（精确匹配优先）；`power_nets`/`ground_nets` 补充
非常规的电源/地网名模式，优先于内置启发式。

**X 实例提升**：profile 的 `models` 同时作用于 **subckt 实例**——
SKY130 等 PDK 惯例把器件写成 `X0 d g s b sky130_fd_pr__nfet_01v8
w=.. l=..`，匹配 profile 的 X 实例会被提升为对应原生器件（MOS 取
前 4 个节点为 d/g/s/b，R/C/L/diode 取前 2 个节点）；netlist 里真实
定义过的 subckt 永远优先。仓库自带 `profiles/sky130.json` 可直接用：

```console
cktdetect design.spice --pdk-profile profiles/sky130.json
```

### 4.4 层次化 netlist

`.subckt` 层次自动处理：报告同时给出顶层展平分析和**逐 subckt 分类**
（`subckt_analysis` 字段），同一 subckt 多次实例化只分析一次；
`composition` 字段统计各 subckt 的实例数量。数百器件的层次化设计
毫秒级完成。

## 5. 输出报告详解

| 字段 | 内容 |
|---|---|
| `classification` | 电路类型结论列表，按置信度降序；每项含 `type`、`confidence`、`evidence`。无结论时为单个 `unknown` |
| `net_roles` | 每个 net 的角色：`power` / `ground` / `bias` / `signal`，附证据 |
| `device_roles` | 每个晶体管的角色（见 5.1），附证据 |
| `structures` | 识别出的结构：电流镜（reference/outputs/电流比例）、差分对（inputs/outputs/tail） |
| `cross_coupled` | 交叉耦合对（正反馈 2-cycle） |
| `tanks` | LC 谐振腔（`parallel` / `differential` / `single_ended` 三种形态） |
| `branches` | DC 支路分解：每条"腿"的器件栈、所触电源轨、内部网、分叉网 |
| `stage_edges` | 腿级信号流边（drain→gate 直连或经电容 AC 耦合，含反相极性） |
| `non_dc_devices` | 不导直流的器件（电容等） |
| `subckt_analysis` | 每个 subckt 的独立分类结论 |
| `composition` | 各 subckt 实例数统计 |
| `warnings` | 解析与分析过程中的全部告警 |

### 5.1 器件角色一览

`diff_input`（差分输入管）、`common_source`（共源放大管）、
`amplifier`（一般放大管）、`source_follower`（源跟随器）、
`cascode`、`diode`（二极管接法）、`mirror_reference` / `mirror_output`
（镜像参考/输出）、`current_source` / `current_sink`（电流源/沉）、
`tail_current_source`（尾电流源）、`bias_gated`（偏置栅控）、
`rail_tied`（栅接轨）、`unknown`。

## 6. 支持的电路类型

置信度阈值 0.6，低于阈值输出 `unknown`。

### 放大器类

| `type` 输出 | 电路 | 置信度 |
|---|---|---|
| `single_stage_ota` | 单级（5T）OTA：差分对 + 镜像负载 + 尾电流源 | 0.70–0.90 |
| `two_stage_ota` | 两级 Miller OTA（检出 Miller 补偿电容） | 0.75–0.95 |
| `folded_cascode_ota` | 折叠 cascode（对管输出折入反极性 cascode） | 0.75–0.90 |
| `telescopic_ota` | 套筒 cascode（对管输出叠同极性 cascode） | 0.75–0.90 |
| `fully_differential_ota` | 全差分 OTA，可检出电阻式 CMFB | 0.75–0.95 |
| `common_source_amplifier` | 单管共源增益级（含负载类型证据） | 0.65–0.80 |
| `rail_to_rail_input_stage` | 轨到轨输入级（互补双差分对共享输入） | 0.80–0.85 |
| `class_ab_output_stage` | class-AB 推挽输出级（互补对、独立栅驱动） | 0.75–0.80 |
| `buffer` | 源跟随器缓冲器 | 0.70 |

### 比较器类

| `type` 输出 | 电路 | 置信度 |
|---|---|---|
| `comparator` | 静态 latch 比较器（差分对 + 交叉耦合负载） | 0.75–0.80 |
| `strongarm_comparator` | StrongARM 动态比较器（时钟尾管 + 预充管 + 再生 latch） | 0.85–0.90 |

### 偏置与电源管理类

| `type` 输出 | 电路 | 置信度 |
|---|---|---|
| `current_mirror_bias` | 电流镜偏置网络（simple/cascode，MOS 或 BJT） | 0.75–0.80 |
| `beta_multiplier_bias` | beta-multiplier / constant-gm 自偏置基准 | 0.80–0.85 |
| `ldo` | LDO（误差放大器 + pass 管 + 电阻分压负反馈） | 0.85–0.90 |
| `bandgap_core` | bandgap ΔVbe 核（含结面积比证据） | 0.75–0.90 |

### 射频与振荡器类

| `type` 输出 | 电路 | 置信度 |
|---|---|---|
| `lc_vco` | LC 振荡器（交叉耦合负阻 + tank） | 0.85–0.90 |
| `ring_oscillator` | 环形振荡器（奇数级反相器闭环） | 0.85–0.90 |
| `lna` | 低噪放（源极电感退化 + 栅匹配 + cascode） | 0.75–0.95 |
| `gilbert_mixer` | Gilbert 混频器（三层栈交叉连接开关四管） | 0.85–0.90 |

### 开关与数据转换类

| `type` 输出 | 电路 | 置信度 |
|---|---|---|
| `sample_and_hold` | 采样保持（pass 开关 + 高阻保持电容节点 + 缓冲器） | 0.75–0.85 |
| `switched_capacitor_circuit` | 开关电容电路（≥2 时钟相位 × ≥3 pass 开关 + 开关网电容；内嵌放大器作为次级结论保留） | 0.85 |
| `dickson_charge_pump` | Dickson 电荷泵（diode 链 + 交替时钟泵电容） | 0.80–0.85 |
| `r2r_ladder` | R-2R DAC 梯形电阻网络（骨架 R + 每节点 2R 支路） | 0.85–0.90 |

### 无源网络类（无晶体管电路走独立分析路径）

| `type` 输出 | 电路 | 置信度 |
|---|---|---|
| `passive_filter_lowpass` / `_highpass` / `_bandpass` | RC/LC 梯形滤波器，附阶数证据 | 0.80 |
| `resistive_divider` | 电阻分压器，附 tap 网证据 | 0.75 |

### 系统级（组合识别）

对含 subckt 实例的设计，在"块实例图"（实例 + 各自的分类结果 +
端口连接）上运行系统级 verifier，结论排在块级结论之前：

| `type` 输出 | 判据 | 置信度 |
|---|---|---|
| `pll` | 振荡器块 + 鉴相/电荷泵块 + 环路滤波块闭合成控制环（三段共享网互不相同），外部参考输入加分 | 0.80–0.85 |
| `flash_adc` | ≥3 个比较器类实例 + 电阻梯抽头分别接不同比较器 + 比较器共享输入网 | 0.85–0.90 |
| `vco_stage_chain` | ≥3 个同 subckt 压控反相级实例连成**开链**（闭链是环振，由平坦级规则处理），全体共享非轨控制网（区别于普通 buffer 链），链端开放/出端口 | 0.80 |

### 特殊输出

| `type` 输出 | 含义 | 置信度 |
|---|---|---|
| `template:<label>` | 与模板库中参考 netlist 图同构 | 0.97 |
| `unknown` | 无 verifier 达到阈值 | 0.0 |

每种类型在 `tests/benchmarks/` 都有对应的基准 netlist（正例与反例），
可作为格式参考。

## 7. 多个结论怎么读

`classification` 可能含多个超过阈值的结论（例如 bandgap 电路同时含有
一个镜像偏置结构）。**取第一个作为电路类型**；靠后的结论描述的是
电路中真实存在的子结构，不是误报。系统级结论（`pll`/`flash_adc`）
永远排在块级结论之前——它们描述整体，块级结论描述其组成部分
（如 PLL 报告中随后会出现展平后的 `ring_oscillator`）。

## 8. 模板库

对于精确已知的拓扑，可以完全不写规则：

1. 建一个目录，把带标签的参考 netlist 放进去，**文件名即标签**：
   `templates/classic_5t_ota.sp`；
2. 运行 `cktdetect design.sp --templates templates/`。

匹配基于图同构签名：器件改名、net 改名、MOS 源漏交换、语句顺序变化
都不影响匹配；命中时输出 `template:classic_5t_ota`（置信度 0.97），
排在规则结论之前。模板文件支持 SPICE 与 Spectre（`.sp`/`.scs`）。

## 9. HTML 可视化报告

```console
cktdetect design.sp --html report.html
```

生成自包含 HTML（无外部依赖，直接浏览器打开）：分类结论卡片（置信度
条 + 证据列表）、按角色着色的 DC 支路图（电源轨在顶、地轨在底、分叉
网标注）、结构表、net 角色表、逐 subckt 分类表、告警列表。

## 10. netlist 结构对比

```console
cktdetect a.sp --diff b.sp -o diff.json
```

在结构层而非文本层对比两个电路，输出：

- `classification`：两边的类型结论及是否一致；
- `common_structures`：双方共有的结构（如 `differential_pair(pol=n,tailed)`）；
- `a_only_structures` / `b_only_structures`：一方独有的结构；
- `device_count_delta`：器件数量差异。

典型用途：确认两个 OTA 变体"输入级相同，仅补偿方式不同"。

## 11. 已知限制

- **明确输出 unknown**：数字标准单元（范围外——反相器会被内部识别，
  用于环形振荡器检测和防误报，但纯逻辑链仍输出 unknown）、
  translinear 环路。SC 电路整体可识别（`switched_capacitor_circuit`）
  但滤波器/积分器子类型未细分；开环 VCO 级链可识别
  （`vco_stage_chain`）但要求级为 subckt 实例形式。
- **归一化说明**：并联同构 MOS 自动合并（m 累加）；同栅串联栈自动
  合并（L 相加，真实 PDK 里拆分的长沟道管）；经 cascode 的复合
  diode 镜像（cascoded mirror）可识别，记录为 `variant: cascode`。
- 极性无法推断的 MOS 会降级处理（见 4.3，可用 PDK profile 解决）。
- 无源梯形分析要求简单梯形（每级单一串联路径），复杂多端口无源网络
  不适用。
- 验收基于教科书风格电路；真实 PDK netlist（dummy 器件、特殊连接）
  可能需要扩充规则——欢迎把误判样本做成反例基准。

## 12. 常见问题

**Q: 报告说 `cannot infer MOS polarity`？**
netlist 里没有 `.model` 卡且模型名不含 n/p 特征。三个办法：写一个
PDK profile（`--pdk-profile`，推荐，见 4.3）、补 `.model` 卡、或把
模型名改成 `nch`/`pch` 风格。

**Q: 明明是 OTA 却输出 unknown？**
按顺序检查：`net_roles` 里电源/地是否识别对（非常规轨名依赖 bulk
连接投票，flat 电路建议保留电压源）；`structures` 里差分对/镜像是否
找到；再对照第 6 章的 Required 条件。`classification` 之外的中间结果
就是为排查设计的。

**Q: 第一行器件被吃掉了？**
标准 SPICE 把第一行当标题。让 netlist 以注释行（`*`）开头即可避开。

**Q: 想加一种新电路类型？**
两条路：精确拓扑 → 放模板（第 8 章，零代码）；结构变体族 → 在
`cktdetect/classify/verifiers/` 加一个 verifier 函数并注册到
`engine.py`，同时在 `tests/benchmarks/` 加正例与反例。
