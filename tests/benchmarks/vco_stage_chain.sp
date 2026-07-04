* open vco stage chain: 4 controlled inverting stages, loop closes off-chip
.subckt inv_stage vbias vin vout vdd vss
Mn vout vin vss vss nch W=2u L=0.1u
Mp vout vbias vdd vdd pch W=4u L=0.1u
.ends
X1 vb a b vdd 0 inv_stage
X2 vb b c vdd 0 inv_stage
X3 vb c d vdd 0 inv_stage
X4 vb d e vdd 0 inv_stage
Vdd vdd 0 1.2
Vb vb 0 0.6
.end
