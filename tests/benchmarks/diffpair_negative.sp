* NOT a differential pair: gates tied together (pseudo pair)
Vdd vdd 0 1.8
Vg g1 0 0.9
Rt tail 0 10k
M1 o1 g1 tail 0 nch W=2u L=1u
M2 o2 g1 tail 0 nch W=2u L=1u
R1 vdd o1 10k
R2 vdd o2 10k
.end
