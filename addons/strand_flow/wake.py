"""Deterministic, group-centred wake deformation in normalized guide coordinates."""
import math

def smooth(x):
    x=max(0.0,min(1.0,x));return x*x*(3-2*x)

def weight(t,s):
    if t<s.wake_start or t>s.wake_end:return 0.0
    span=s.wake_end-s.wake_start
    if span<=1e-6:return 0.0
    u=(t-s.wake_start)/span
    enter=smooth(u/max(s.wake_fade_in,1e-6))
    leave=smooth((1-u)/s.wake_fade_out) if s.wake_fade_out>0 else 1.0
    return enter*leave*s.wake_amount

def deform(path,center,basis,s,theta):
    result=[]
    for i,(p,c,(n,v)) in enumerate(zip(path,center,basis)):
        t=i/(len(path)-1);w=weight(t,s)
        if w==0:result.append(p);continue
        delta=p-c
        radial=n*delta.dot(n)+v*delta.dot(v)
        # Almost-centre strands get a stable direction instead of a singular normalization.
        fallback=n*math.cos(theta)+v*math.sin(theta)
        direction=(radial+fallback*max(s.wake_spread*.02,1e-5)).normalized()
        phase=math.tau*(s.wake_frequency*t-s.wake_phase)+theta
        noise=n*math.sin(phase)+v*.65*math.sin(phase*1.71+theta)
        result.append(p+w*(direction*s.wake_spread+noise*s.wake_noise))
    return result
