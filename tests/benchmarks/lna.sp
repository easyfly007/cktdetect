* cascode lna with inductive degeneration and gate matching inductor
Vdd vdd 0 1.2
Vb nbc 0 0.9
Vg nbg 0 0.6
Vin rfin 0 AC 1
Lg rfin g1 5n
Rb nbg g1 10k
M1 x1 g1 s1 0 nch W=50u L=0.1u
Ls s1 0 1n
M2 out nbc x1 0 nch W=50u L=0.1u
Ld vdd out 3n
Cl out 0 200f
.end
