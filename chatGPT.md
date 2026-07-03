# Circuit Topology Foundation Layer（ChatGPT 讨论记录）

你可以把 Circuit Topology Foundation Layer 理解成：

> 把 transistor-level netlist 转换成一个"规范化、分层、带电路语义的图结构"，供上层优化、比较、debug、可视化使用。

它不是"AI 猜电路"，而是 **Graph Algorithm + Constraint Matching + Circuit Rules + Hierarchical Reduction**。严格说甚至不一定叫 AI，更像 EDA 核心算法。

## 目标是什么

例如输入 flat SPICE：

```spice
M1 n1 inp tail 0 nch
M2 n2 inn tail 0 nch
M3 n1 n1 vdd vdd pch
M4 n2 n1 vdd vdd pch
M5 tail vb  0   0 nch
```

第一层不是直接说"这是 OTA"，而是建立 device-net graph：

```
M1:
  D=n1
  G=inp
  S=tail
  B=0
  type=NMOS

M2:
  D=n2
  G=inn
  S=tail
  B=0
  type=NMOS
```

然后逐层推导：

```
Level 0: Device
  M1 M2 M3 M4 M5

Level 1: Primitive Structure
  M1+M2 → matched common-source pair
  M3+M4 → current mirror
  M5    → current-source candidate

Level 2: Functional Block
  M1+M2 → differential pair
  M3+M4 → active load
  M5    → tail current source

Level 3: Architecture
  differential pair
    + current mirror load
    + tail source
  → OTA-like input stage
```

关键点是：**每一级都可以完全 rule-based。**

## 我建议的核心架构

唯一一张主线图可以这样理解：

```
SPICE / OA Netlist
        ↓
[1] Parser
        ↓
Canonical Device IR
        ↓
[2] Electrical Normalization
        ↓
Canonical Circuit Graph
        ↓
[3] Primitive Motif Detection
        ↓
Mirror / Diff Pair / Cascode / Stack
        ↓
[4] Graph Reduction
        ↓
Supernodes / Superdevices
        ↓
[5] Functional Block Detection
        ↓
Bias / Load / Gain Stage / Output Stage
        ↓
[6] Hierarchical Topology IR
        ↓
Compare / Search / Debug / Optimization
```

## 1. Canonical IR：先解决"同一个电路长得不一样"

这是最重要的一层。

比如：

```spice
M1 d g s b nch W=2u M=1
```

和：

```spice
M1a d g s b nch W=1u
M1b d g s b nch W=1u
```

拓扑上可能应该归一成同一种等效结构。

再比如 MOS source/drain 对称问题：

```spice
M1 D=n1 S=n2
```

和

```spice
M1 D=n2 S=n1
```

对于某些 topology matching，不应该直接判不同。

所以 IR 要支持：

```
Device {
    type
    model_family
    terminals {
        gate
        source
        drain
        bulk
    }
    geometry
    multiplicity
    attributes
}
```

然后做：

- net rename normalization
- parallel MOS merge
- series device recognition
- finger normalization
- M factor normalization
- source/drain canonicalization
- hierarchy flatten / preserve 双表示

这一层单独拿出来就已经是很硬的项目。

## 2. Primitive Motif Detection：先识别小结构

不要一开始就识别"这是 folded cascode OTA"。

先识别确定性很高的小 motif。

例如电流镜：

```
M1.g == M2.g
M1.g == M1.d
type(M1) == type(M2)
source_domain(M1) == source_domain(M2)
```

就得到：

```
CurrentMirror {
    reference = M1
    outputs = [M2]
    gate_net = n1
}
```

差分对：

```
type(M1) == type(M2)
M1.s == M2.s
M1.g != M2.g
M1.d != M2.d
```

得到 candidate：

```
CommonSourcePair {
    devices = [M1, M2]
    common_source = tail
    inputs = [inp, inn]
}
```

再结合：

- 参数近似相等
- 两 gate 是 input-like nets
- common source 接 current source
- drain 两侧结构近似对称

置信度越来越高：

```
common-source pair: 0.6
+ matched W/L:      0.1
+ symmetric load:   0.1
+ tail source:      0.15
-------------------------
diff pair:          0.95
```

注意：这个 confidence 完全不需要机器学习。

就是：

```
score = (
    w1 * common_source +
    w2 * matched_geometry +
    w3 * symmetric_drain +
    w4 * tail_bias
)
```

## 3. 最有意思的核心：迭代式 Graph Reduction

我认为这是整个项目最值得做的地方。

第一次扫描：

```
M1 + M2 → DIFF_PAIR_1
M3 + M4 → MIRROR_1
M5      → CURRENT_SOURCE_1
```

然后原图：

```
M1 M2 M3 M4 M5
```

压缩成：

```
DIFF_PAIR_1
MIRROR_1
CURRENT_SOURCE_1
```

再在新图上匹配：

```
DIFF_PAIR
   +
MIRROR_LOAD
   +
TAIL_SOURCE
```

识别成：

```
INPUT_STAGE_1
```

继续 reduction：

```
INPUT_STAGE_1
SECOND_STAGE_1
COMPENSATION_1
```

最后：

```
TWO_STAGE_OTA
```

也就是说：

> 识别 → 压缩 → 再识别 → 再压缩

这和 compiler 的 IR pass 很像，我觉得特别适合你的软件背景。

## 4. 难点在哪里

### 最大难点不是 graph matching，而是"电路等价性"

例如最简单的 current mirror 都可能变成：

- simple mirror
- cascode mirror
- wide-swing mirror
- Wilson-like structure
- multiple outputs
- scaled mirror
- degeneration

差分对也可能：

- NMOS pair
- PMOS pair
- complementary pair
- folded input
- bulk-driven pair
- multi-finger pair
- parallel devices

所以不能写成：

```python
if topology == exact_pattern:
    return "diff_pair"
```

更应该是 **约束匹配**：

```
Pattern: DifferentialPair

Required:
  two transistors
  same polarity
  shared source region
  distinct gate nets

Optional:
  matched W/L
  symmetric drain environment
  tail current source
  input-port connection

Forbidden:
  gate shorted together
```

这就像一个小型 declarative rule engine。

## 5. 我特别建议你加入"结构签名"

每个局部子图生成 signature：

```
M1 neighborhood:

depth=1:
  G → input_net
  S → M2.S, M5.D
  D → M3.D

depth=2:
  ...
```

可以用：

- Weisfeiler–Lehman graph hash
- canonical labeling
- degree signature
- typed-edge signature
- neighborhood hash

例如：

```
device type:
NMOS

terminal degree:
D: 2
G: 1
S: 3
B: VSS

2-hop hash:
8fa291...
```

这样你就能非常快地做：

- 找相似器件
- 找对称支路
- 找重复 block
- 找左右 differential branch
- 找 hierarchy 中重复结构

这部分也完全不需要神经网络。

## 6. 你之前想做的"最大交集子图比较"，正好能并进来

例如两个 OTA：

```
Circuit A
Circuit B
```

经过 normalization 后：

```
A:
  DIFF_PAIR
  MIRROR_LOAD
  TAIL_SOURCE
  SECOND_STAGE
  MILLER_CAP

B:
  DIFF_PAIR
  MIRROR_LOAD
  TAIL_SOURCE
  SECOND_STAGE
  RC_COMPENSATION
```

输出：

```
Common topology:
  input stage
  active load
  tail bias
  second stage

Difference:
  A: pure Miller compensation
  B: nulling-resistor compensation
```

这比 raw netlist diff 高一个层次。

## 我认为最现实的 MVP

不要上来识别 OTA/LDO/PLL。

第一版只做 **MOS Analog Primitive Recognizer**，支持：

- parallel MOS group
- series stack
- diode-connected MOS
- current mirror
- differential pair
- cascode pair
- current source/sink candidate
- symmetric branches

输入：

```
SPICE netlist
```

输出 JSON：

```json
{
  "structures": [
    {
      "type": "differential_pair",
      "devices": ["M1", "M2"],
      "confidence": 0.96,
      "ports": {
        "in_p": "vip",
        "in_n": "vin",
        "tail": "ntail"
      },
      "evidence": [
        "shared_source",
        "same_polarity",
        "matched_geometry",
        "symmetric_drain_context"
      ]
    }
  ]
}
```

然后做一个 SVG/HTML viewer，把识别出来的 block 框起来。

这与你之前的"跨层级 viewer + 框选 group + 电路分组"几乎天然衔接。

## 成功概率判断

我会这样评价：

- **做到 60 分：很有机会。** 识别 mirror、diff pair、cascode、stack、symmetry，完全现实。
- **做到 80 分：有难度但值得。** 加入 hierarchy、normalization、graph reduction、复杂变体。
- **做到 95 分：极难。** 任意 foundry、任意设计风格、任意 custom analog block 都准确理解，基本不现实。

但 EDA 工具根本不需要 95 分才有价值。你完全可以：

- 高 precision
- 低一点 recall
- 允许 unknown

也就是宁可：

```
UNKNOWN_BLOCK
```

也不要错误识别。

---

对你而言，我认为这个项目甚至比"LLM Agent"更值得做。 因为一旦这个 Foundation Layer 做出来，你后面的 **历史优化数据复用、拓扑相似度、跨电路变量映射、自动 debug、PVT root cause、LLM Copilot** 全部可以建立在它上面。

而且结合你已有的 **子图框选、差分对/电流镜识别、最大交集子图、优化轨迹复用** 想法，这不是另起炉灶，实际上可以把你过去几个零散方向统一成一个底座。

如果你想继续，我可以下一步直接给你设计一个真正可编码的 Python 项目架构，包括 CircuitGraph 数据结构、pattern DSL、diff-pair/current-mirror matcher 和 iterative graph reduction 算法。
