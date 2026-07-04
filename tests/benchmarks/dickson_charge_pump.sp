* 4-stage dickson charge pump, diode-connected nmos, two-phase clock
Vdd vdd 0 1.8
Vc1 clk1 0 DC 0 AC 1
Vc2 clk2 0 DC 0 AC 1
M1 vdd vdd n1 0 nch W=4u L=0.5u
M2 n1 n1 n2 0 nch W=4u L=0.5u
M3 n2 n2 n3 0 nch W=4u L=0.5u
M4 n3 n3 out 0 nch W=4u L=0.5u
C1 n1 clk1 100f
C2 n2 clk2 100f
C3 n3 clk1 100f
CL out 0 1p
.end
