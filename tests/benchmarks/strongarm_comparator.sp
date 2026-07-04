* strongarm dynamic comparator
Vdd vdd 0 1.2
Vclk clk 0 0
M0 tail clk 0 0 nch W=8u L=0.1u
M1 x1 vip tail 0 nch W=4u L=0.1u
M2 x2 vin tail 0 nch W=4u L=0.1u
M3 op on x1 0 nch W=4u L=0.1u
M4 on op x2 0 nch W=4u L=0.1u
M5 op on vdd vdd pch W=4u L=0.1u
M6 on op vdd vdd pch W=4u L=0.1u
M7 op clk vdd vdd pch W=2u L=0.1u
M8 on clk vdd vdd pch W=2u L=0.1u
M9 x1 clk vdd vdd pch W=1u L=0.1u
M10 x2 clk vdd vdd pch W=1u L=0.1u
Vip vip 0 0.6
Vin vin 0 0.6
.end
