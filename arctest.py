# -*- coding: utf-8 -*-
"""
Created on Fri Mar  6 09:13:14 2026

@author: SG1295
"""
import numpy as np
from numpy import sqrt,cos,sin,pi,real,imag
import matplotlib.pyplot as plt 
import matplotlib as mpl

p1=-0.0125+0.002j
p2=-0.0045+0.01j
center=-0.0045+0.002j
cw=False

rad = np.abs(p1-center)
angle_start_deg = np.angle(p1-center,deg=True)%360
angle_end_deg = np.angle(p2-center,deg=True)%360

print(f'Radius: {rad}\nStart angle: {angle_start_deg} deg\nEnd angle: {angle_end_deg} deg')

if cw:
    arc = mpl.patches.Arc((real(center),imag(center)), width=2*rad, height=2*rad, 
                          angle=0, theta1=angle_end_deg, theta2=angle_start_deg,color='b',lw=1.5)
else:
    arc = mpl.patches.Arc((real(center),imag(center)), width=2*rad, height=2*rad, 
                          angle=0, theta1=angle_start_deg, theta2=angle_end_deg,color='b',lw=1.5)

fig,ax = plt.subplots()
ax.set_aspect('equal')
ax.set_box_aspect(1)
ax.plot(np.real(p1),np.imag(p1),'b+')
ax.plot(np.real(p2),np.imag(p2),'r+')
ax.plot(np.real(center),np.imag(center),'kx')
ax.add_patch(arc)


