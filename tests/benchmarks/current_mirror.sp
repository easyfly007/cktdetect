* simple nmos current mirror with resistive load
Vdd vdd 0 1.8
Ibias vdd nref 10u
M1 nref nref 0 0 nch W=2u L=1u
M2 nout nref 0 0 nch W=4u L=1u M=2
Rload vdd nout 10k
.end
