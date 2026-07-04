* fully differential ota with resistive common-mode feedback
Vdd vdd 0 1.8
Vb nb 0 0.7
Vbp nbp 0 1.0
M1 op vin tail 0 nch W=10u L=0.5u
M2 on vip tail 0 nch W=10u L=0.5u
M5 tail nb 0 0 nch W=8u L=1u
M3 op nbp vdd vdd pch W=12u L=1u
M4 on nbp vdd vdd pch W=12u L=1u
R1 op vcm 100k
R2 on vcm 100k
M6 tail vcm 0 0 nch W=2u L=1u
Vip vip 0 0.9
Vin vin 0 0.9
CL1 op 0 1p
CL2 on 0 1p
.end
