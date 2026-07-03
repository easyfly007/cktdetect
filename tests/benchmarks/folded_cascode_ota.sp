* folded cascode ota, nmos input pair, pmos folding cascodes
Vdd vdd 0 1.8
Vb1 nbp 0 1.2
Vb2 nbc 0 0.9
Ib vdd nbn 20u
Mb nbn nbn 0 0 nch W=4u L=1u
M1 f1 vip tail 0 nch W=10u L=0.5u
M2 f2 vin tail 0 nch W=10u L=0.5u
M5 tail nbn 0 0 nch W=8u L=1u
M6 f1 nbp vdd vdd pch W=20u L=1u
M7 f2 nbp vdd vdd pch W=20u L=1u
M8 o1 nbc f1 vdd pch W=20u L=1u
M9 vout nbc f2 vdd pch W=20u L=1u
M10 o1 o1 0 0 nch W=6u L=1u
M11 vout o1 0 0 nch W=6u L=1u
Vip vip 0 0.9
Vin vin 0 0.9
CL vout 0 2p
.end
