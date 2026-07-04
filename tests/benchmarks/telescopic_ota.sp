* telescopic cascode ota: nmos pair, nmos cascodes, pmos mirror load
Vdd vdd 0 1.8
Vb nb 0 0.7
Vbc nbc 0 1.0
M1 x1 vip tail 0 nch W=10u L=0.5u
M2 x2 vin tail 0 nch W=10u L=0.5u
M5 tail nb 0 0 nch W=8u L=1u
M3 o1 nbc x1 0 nch W=10u L=0.5u
M4 vout nbc x2 0 nch W=10u L=0.5u
M6 o1 o1 vdd vdd pch W=12u L=1u
M7 vout o1 vdd vdd pch W=12u L=1u
Vip vip 0 0.9
Vin vin 0 0.9
CL vout 0 2p
.end
