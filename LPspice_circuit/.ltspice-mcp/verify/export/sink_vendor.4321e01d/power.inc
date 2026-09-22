* Original PDF parts: U1/U2/D5 use clearly named NON-VENDOR surrogates.
XU1 V_BUS BONE_P PGND FB ST715_APPROX
R1 BONE_P FB_TOP 560k
R2 FB_TOP FB 6.8k
R3 FB PGND 100k
C7 V_BUS PGND 100n
C8 BONE_P PGND 470n
XU2 BONE_P V3V3 PGND MCP1703A33_APPROX
C9 BONE_P PGND 100n
C10 V3V3 PGND 1u
* R4 is a 0 ohm net tie from PGND to GND on the PDF. LTspice rejects a
* literal 0 ohm ("Resistance must not be zero"), so it is 1 milliohm here;
* the resulting PGND-GND offset is microvolts at these currents.
R4 PGND 0 1m
XD5 V_BUS PGND VESD16_APPROX
