* 3-stage cmos ring oscillator
Vdd vdd 0 1.2
M1 n2 n1 0 0 nch W=2u L=0.1u
M2 n2 n1 vdd vdd pch W=4u L=0.1u
M3 n3 n2 0 0 nch W=2u L=0.1u
M4 n3 n2 vdd vdd pch W=4u L=0.1u
M5 n1 n3 0 0 nch W=2u L=0.1u
M6 n1 n3 vdd vdd pch W=4u L=0.1u
C1 n1 0 10f
.end
