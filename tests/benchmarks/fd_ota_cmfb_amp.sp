* fully differential ota with an ACTIVE cmfb error amplifier
* trap: the cmfb amp (m6..m10) is itself a 5t ota with mirror load and
* must not be claimed as the main amplifier
Vdd vdd 0 1.8
Vb nb 0 0.7
Vcm vcm 0 0.9
M1 op vin tail 0 nch W=10u L=0.5u
M2 on vip tail 0 nch W=10u L=0.5u
M5 tail nb 0 0 nch W=8u L=1u
M3 op cmfb vdd vdd pch W=12u L=1u
M4 on cmfb vdd vdd pch W=12u L=1u
R1 op cms 100k
R2 on cms 100k
M6 x1 cms ctail 0 nch W=4u L=0.5u
M7 cmfb vcm ctail 0 nch W=4u L=0.5u
M8 x1 x1 vdd vdd pch W=8u L=1u
M9 cmfb x1 vdd vdd pch W=8u L=1u
M10 ctail nb 0 0 nch W=2u L=2u
Vip vip 0 0.9
Vin vin 0 0.9
CL1 op 0 1p
CL2 on 0 1p
.end
