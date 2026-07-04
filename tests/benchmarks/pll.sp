* charge-pump pll: current-starved ring vco + pfd/cp + rc loop filter
.subckt ring_osc vctl osc vdd vss
Mp1 n2 osc vctl vdd pch W=4u L=0.1u
Mn1 n2 osc vss vss nch W=2u L=0.1u
Mp2 n3 n2 vctl vdd pch W=4u L=0.1u
Mn2 n3 n2 vss vss nch W=2u L=0.1u
Mp3 osc n3 vctl vdd pch W=4u L=0.1u
Mn3 osc n3 vss vss nch W=2u L=0.1u
.ends
.subckt pfd_cp ref fb icp vdd vss
Mup icp ref vdd vdd pch W=4u L=0.5u
Mdn icp fb vss vss nch W=2u L=0.5u
.ends
.subckt loop_filter icp vctl vss
R1 icp vctl 10k
C1 vctl vss 10p
.ends
Xosc vctl osc vdd 0 ring_osc
Xpd ref osc icp vdd 0 pfd_cp
Xlf icp vctl 0 loop_filter
Vdd vdd 0 1.2
Vref ref 0 PULSE(0 1.2 0 1n 1n 5n 10n)
.end
