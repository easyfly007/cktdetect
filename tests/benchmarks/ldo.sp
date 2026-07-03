* simple pmos ldo: 5t error amp + pass device + resistive feedback
Vdd vdd 0 3.3
Vref vref 0 1.2
Vb nb 0 0.7
M1 n1 vref tail 0 nch W=4u L=0.5u
M2 na fb tail 0 nch W=4u L=0.5u
M3 n1 n1 vdd vdd pch W=8u L=1u
M4 na n1 vdd vdd pch W=8u L=1u
M5 tail nb 0 0 nch W=2u L=2u
Mp vout na vdd vdd pch W=200u L=0.5u
R1 vout fb 100k
R2 fb 0 100k
CL vout 0 1u
Rl vout 0 100
.end
