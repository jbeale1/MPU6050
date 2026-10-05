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
```

"serve2.py" output (comparing two different types: MPU6050 and ADXL313)
```
epoch,n,MPU_X,MPU_Y,MPU_Z,degC,ADXL_X,ADXL_Y,ADXL_Z,samples
1791228603,1,1.0272,0.7141,0.5628,23.51,0.0036,0.0317,1.0121,1000
1791228607,2,1.0272,0.7141,0.563,23.52,0.0036,0.0316,1.0117,1000
1791228610,3,1.0272,0.7143,0.563,23.53,0.0033,0.0318,1.0121,1000
1791228613,4,1.0272,0.7141,0.5626,23.54,0.0033,0.032,1.0116,1000
1791228616,5,1.0273,0.7141,0.5628,23.54,0.0032,0.032,1.012,1000
```
