# cktdetect 支持的电路类型清单

本文档是**当前实现**的权威清单（与 `cktdetect/classify/verifiers/` 和
`tests/benchmarks/` 同步维护；新增 verifier 时必须同步更新本表）。
DESIGN.md 第 4 节是设计判据，本文档记录实际输出。

分类结果出现在 JSON 报告的 `classification` 字段，按置信度排序；
低于阈值 **0.6** 时输出 `unknown`，绝不猜测。

## 一、电路类型（verifier 输出）

### 放大器类

| 输出类型字符串 | 电路 | 置信度 | 基准 netlist |
|---|---|---|---|
| `single_stage_ota` | 单级（5T）OTA：差分对 + 镜像负载 + 尾电流源 | 0.70–0.90 | five_t_ota.sp |
| `two_stage_ota` | 两级 Miller OTA：上者 + 第二级 CS + Miller 电容 | 0.75–0.95 | two_stage_ota.sp |
| `folded_cascode_ota` | 折叠 cascode：对管输出折入**反极性** cascode | 0.75–0.90 | folded_cascode_ota.sp |
| `telescopic_ota` | 套筒 cascode：对管输出直接叠**同极性** cascode | 0.75–0.90 | telescopic_ota.sp |
| `fully_differential_ota` | 全差分 OTA：双输出电流源负载，可检出电阻 CMFB | 0.75–0.95 | fd_ota_cmfb.sp |
| `buffer` | 源跟随器缓冲器（无增益级、无差分对） | 0.70 | source_follower.sp |

### 比较器类

| 输出类型字符串 | 电路 | 置信度 | 基准 netlist |
|---|---|---|---|
| `comparator` | 静态 latch 比较器：差分对 + 交叉耦合再生负载 | 0.75–0.80 | latch_comparator.sp |
| `strongarm_comparator` | StrongARM 动态比较器：时钟尾管 + 预充管 + 再生 latch | 0.85–0.90 | strongarm_comparator.sp |

### 偏置与电源管理类

| 输出类型字符串 | 电路 | 置信度 | 基准 netlist |
|---|---|---|---|
| `current_mirror_bias` | 电流镜偏置网络（simple/cascode，MOS 或 BJT） | 0.75–0.80 | current_mirror.sp, cascode_mirror.sp |
| `beta_multiplier_bias` | beta-multiplier / constant-gm 自偏置基准 | 0.80–0.85 | beta_multiplier.sp |
| `ldo` | LDO：误差放大器 + pass 管 + 电阻分压负反馈 | 0.85–0.90 | ldo.sp |
| `bandgap_core` | bandgap ΔVbe 核：BJT 对 + 发射极电阻 + 镜像强制电流 | 0.75–0.90 | bandgap_core.sp |

### 射频类

| 输出类型字符串 | 电路 | 置信度 | 基准 netlist |
|---|---|---|---|
| `lc_vco` | LC 振荡器：交叉耦合负阻对 + LC tank | 0.85–0.90 | lc_vco.sp |
| `lna` | 低噪放：源极电感退化 + 栅匹配电感 + cascode + 感性负载 | 0.75–0.95 | lna.sp |
| `gilbert_mixer` | Gilbert 混频器：跨导对 + 交叉连接开关四管三层栈 | 0.85–0.90 | gilbert_mixer.sp |

### 无源网络类（无晶体管电路）

| 输出类型字符串 | 电路 | 置信度 | 基准 netlist |
|---|---|---|---|
| `passive_filter_lowpass` | RC/LC 低通梯形（附阶数证据） | 0.80 | rc_lowpass.sp, lc_lowpass_pi.sp |
| `passive_filter_highpass` | RC/LC 高通梯形 | 0.80 | rc_highpass.sp |
| `passive_filter_bandpass` | 混合型带通/带阻梯形 | 0.80 | rlc_bandpass.sp |
| `resistive_divider` | 电阻分压器（附 tap 网证据） | 0.75 | r_divider.sp |

### 特殊输出

| 输出类型字符串 | 含义 | 置信度 |
|---|---|---|
| `template:<label>` | 与 `--templates` 目录中某参考 netlist 图同构（改名 / S-D 交换不变） | 0.97 |
| `unknown` | 无 verifier 达到阈值——宁可不识别，不可误识别 | 0.0 |

## 二、结构级标注（`structures` 等字段，独立于分类输出）

| 字段 | 内容 |
|---|---|
| `structures` | `current_mirror`（reference/outputs/比例）、`differential_pair`（inputs/outputs/tail） |
| `cross_coupled` | 交叉耦合对（正反馈 2-cycle） |
| `tanks` | LC tank：`parallel` / `differential` / `single_ended` 三种形态 |
| `branches` | DC 支路分解（器件栈、所触轨、分叉网） |
| `stage_edges` | 腿级信号流边（dc 直连 / ac 电容耦合，含反相极性） |

## 三、器件角色（`device_roles` 字段）

`diff_input`、`common_source`、`amplifier`、`source_follower`、
`cascode`、`diode`、`mirror_reference`、`mirror_output`、
`current_source`、`current_sink`、`tail_current_source`、
`bias_gated`、`rail_tied`、`unknown`

## 四、net 角色（`net_roles` 字段）

`power` / `ground` / `bias` / `signal`

## 五、明确不支持（输出 unknown）

- 数字标准单元（inverter/NAND/latch 等，范围外，见 bulk_vote.sp 反例）
- switched-cap 电路（DC 支路被开关切断）
- translinear / 电流模复杂环路
- 大量 pass-gate 的模拟开关阵列

## 六、反例基准（防误报回归）

| 文件 | 验证的"不是" |
|---|---|
| diffpair_negative.sp | 栅极短接的伪差分对 → 不是差分对，unknown |
| bulk_vote.sp | 反相器链 → 不是任何模拟类型，unknown |
| cascode_mirror.sp | 源不同网的栅负载 → 不报为 mirror 输出 |
| bjt 无退化镜像（test_m3 内联） | 两个无退化 BJT → 不是 bandgap |
| 交叉验证（test_m6） | telescopic≠folded、StrongARM≠静态比较器、单端 OTA≠全差分 |
