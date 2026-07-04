* sample-and-hold: nmos pass switch, hold cap, follower buffer
Vdd vdd 0 1.8
Vclk clk 0 0
Vin in 0 DC 0.9 AC 1
Ms hold clk in 0 nch W=4u L=0.1u
Ch hold 0 1p
Mb vdd hold out 0 nch W=10u L=0.5u
Vb nb 0 0.7
Mload out nb 0 0 nch W=2u L=2u
.end
