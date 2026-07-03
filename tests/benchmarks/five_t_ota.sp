five transistor ota (hierarchical)
.subckt ota5 vip vin vout ibias vdd vss
M1 n1 vip tail vss nch W=4u L=0.5u
M2 vout vin tail vss nch W=4u L=0.5u
M3 n1 n1 vdd vdd pch W=8u L=1u
M4 vout n1 vdd vdd pch W=8u L=1u
M5 tail ibias vss vss nch W=2u L=2u
M6 ibias ibias vss vss nch W=2u L=2u
.ends
Xota inp inn out nbias vdd 0 ota5
Vdd vdd 0 1.8
Ib vdd nbias 10u
Vip inp 0 0.9
Vin inn 0 0.9
CL out 0 1p
.end
