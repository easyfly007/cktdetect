* nmos source follower buffer with current-sink load
Vdd vdd 0 1.8
Vb nb 0 0.7
Vin in 0 1.2
M1 vdd in out 0 nch W=10u L=0.5u
M2 out nb 0 0 nch W=2u L=2u
CL out 0 1p
.end
