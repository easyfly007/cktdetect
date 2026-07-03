* two inverting stages with nonstandard rail names
* exercises bulk-vote rail classification
Vp rail_hi 0 1.2
M1 out1 in rail_hi rail_hi pch W=2u L=0.2u
M2 out1 in rail_lo rail_lo nch W=1u L=0.2u
M3 out2 out1 rail_hi rail_hi pch W=2u L=0.2u
M4 out2 out1 rail_lo rail_lo nch W=1u L=0.2u
.end
