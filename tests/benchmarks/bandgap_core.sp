* bandgap ptat core: delta-vbe pnp pair with pmos mirror
.model pnp1 pnp
Vdd vdd 0 3.3
M1 ea nb vdd vdd pch W=10u L=1u
M2 nb nb vdd vdd pch W=10u L=1u
Q1 0 0 ea pnp1
Q2 0 0 eb pnp1 area=8
R1 nb eb 50k
.end
