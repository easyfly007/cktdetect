* two stage miller ota (flat, .model cards, .param, continuation)
.param wl=5u
.model nm nmos (level=1 vto=0.5)
.model pm pmos (level=1 vto=-0.5)
Vdd vdd 0 3.3
Vb  nb  0 0.7
M1 n1 vip tail 0 nm W=wl L=1u
M2 n2 vin tail 0 nm W=wl L=1u
M3 n1 n1 vdd vdd pm W=10u L=1u
M4 n2 n1 vdd vdd pm W=10u L=1u
M5 tail nb 0 0 nm W=2u L=2u
M6 vout n2 vdd vdd pm
+ W=20u L=1u
M7 vout nb 0 0 nm W=4u L=2u
Cc n2 vout 2p
CL vout 0 5p
.end
