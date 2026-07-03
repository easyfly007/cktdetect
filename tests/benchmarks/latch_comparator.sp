* comparator core: diff pair with cross-coupled regenerative load
Vdd vdd 0 1.8
Vb nb 0 0.7
M1 o1 vip tail 0 nch W=4u L=0.5u
M2 o2 vin tail 0 nch W=4u L=0.5u
M5 tail nb 0 0 nch W=2u L=1u
M3 o1 o2 vdd vdd pch W=4u L=0.5u
M4 o2 o1 vdd vdd pch W=4u L=0.5u
Vip vip 0 0.9
Vin vin 0 0.9
.end
