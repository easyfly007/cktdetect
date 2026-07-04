* cascoded nmos current mirror: diode connection runs through the cascode
Vdd vdd 0 1.8
Ib vdd g1 10u
Vb cb 0 1.0
Mc g1 cb x1 0 nch W=2u L=1u
Mb x1 g1 0 0 nch W=2u L=1u
Mo o1 g1 0 0 nch W=4u L=1u
Mco nout cb o1 0 nch W=4u L=1u
Rload vdd nout 10k
.end
