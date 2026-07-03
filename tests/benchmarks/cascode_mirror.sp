* cascode nmos current mirror
Vdd vdd 0 1.8
Ib vdd n1 10u
M1 n1 n1 n2 0 nch W=2u L=1u
M2 n2 n2 0 0 nch W=2u L=1u
M3 nout n1 n3 0 nch W=2u L=1u
M4 n3 n2 0 0 nch W=2u L=1u
Rload vdd nout 10k
.end
