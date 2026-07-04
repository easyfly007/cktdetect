* rail-to-rail input stage: complementary differential pairs
Vdd vdd 0 1.8
Vbn nbn 0 0.7
Vbp nbp 0 1.1
M1 xn1 vip tailn 0 nch W=10u L=0.5u
M2 xn2 vin tailn 0 nch W=10u L=0.5u
M5 tailn nbn 0 0 nch W=8u L=1u
M3 xp1 vip tailp vdd pch W=20u L=0.5u
M4 xp2 vin tailp vdd pch W=20u L=0.5u
M6 tailp nbp vdd vdd pch W=16u L=1u
R1 xn1 vdd 10k
R2 xn2 vdd 10k
R3 xp1 0 10k
R4 xp2 0 10k
Vip vip 0 0.9
Vin vin 0 0.9
.end
