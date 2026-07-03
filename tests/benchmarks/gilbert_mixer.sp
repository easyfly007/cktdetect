* gilbert cell mixer: gm pair + switching quad + resistive loads
Vdd vdd 0 1.8
Vb nb 0 0.7
M1 x1 rfp tail 0 nch W=20u L=0.2u
M2 x2 rfn tail 0 nch W=20u L=0.2u
M5 tail nb 0 0 nch W=10u L=0.5u
M3 op lop x1 0 nch W=10u L=0.2u
M4 on lon x1 0 nch W=10u L=0.2u
M6 on lop x2 0 nch W=10u L=0.2u
M7 op lon x2 0 nch W=10u L=0.2u
R1 vdd op 1k
R2 vdd on 1k
Vrfp rfp 0 0.8
Vrfn rfn 0 0.8
Vlop lop 0 1.2
Vlon lon 0 1.2
.end
