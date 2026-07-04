* flash adc front-end: reference ladder + strongarm comparator array
.subckt comp clk vin vref op on vdd vss
M0 tail clk vss vss nch W=8u L=0.1u
M1 x1 vin tail vss nch W=4u L=0.1u
M2 x2 vref tail vss nch W=4u L=0.1u
M3 op on x1 vss nch W=4u L=0.1u
M4 on op x2 vss nch W=4u L=0.1u
M5 op on vdd vdd pch W=4u L=0.1u
M6 on op vdd vdd pch W=4u L=0.1u
M7 op clk vdd vdd pch W=2u L=0.1u
M8 on clk vdd vdd pch W=2u L=0.1u
.ends
Rl0 vrefhi t2 1k
Rl1 t2 t1 1k
Rl2 t1 t0 1k
Rl3 t0 0 1k
Xc0 clk vin t0 o0p o0n vdd 0 comp
Xc1 clk vin t1 o1p o1n vdd 0 comp
Xc2 clk vin t2 o2p o2n vdd 0 comp
Vhi vrefhi 0 1.2
Vin vin 0 0.6
Vclk clk 0 0
Vdd vdd 0 1.2
.end
