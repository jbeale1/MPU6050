Utility code to exercise MPU-6050 MEMS accelerometer using a Pi Pico-W (original version) to average together a few seconds 
of readings of the accel sensor (in units of 'g') and present the data to the LAN on a webpage.
Example output is as shown below:

```
# Start: 2026-09-24 02:19:25  Last: 2026-09-24 02:20:18
epoch,n,X,Y,Z,degC,samples
1790216365,1,0.016,-0.012,0.949,22.37,1000
1790216368,2,0.016,-0.012,0.948,22.37,1000
1790216371,3,0.016,-0.012,0.949,22.38,1000
1790216373,4,0.015,-0.012,0.948,22.38,1000
1790216376,5,0.016,-0.012,0.948,22.37,1000

# Start: 2026-09-24 02:36:17  Last: 2026-09-24 02:37:09
epoch,n,X,Y,Z,degC,samples
1790217377,1,0.026,-0.025,-1.095,22.78,1000
1790217379,2,0.026,-0.025,-1.095,22.78,1000
1790217382,3,0.026,-0.025,-1.095,22.79,1000
1790217385,4,0.026,-0.025,-1.095,22.79,1000
1790217388,5,0.026,-0.025,-1.095,22.78,1000
```
