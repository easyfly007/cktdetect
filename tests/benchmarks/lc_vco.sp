* nmos cross-coupled lc vco
Vdd vdd 0 1.2
Vb nb 0 0.6
L1 vdd o1 2n
L2 vdd o2 2n
C1 o1 o2 500f
M1 o1 o2 tail 0 nch W=20u L=0.1u
M2 o2 o1 tail 0 nch W=20u L=0.1u
M5 tail nb 0 0 nch W=10u L=0.5u
.end
