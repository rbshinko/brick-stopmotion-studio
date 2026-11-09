import sys, glob, os, json
import numpy as np
from PIL import Image
def st(paths):
    L,S,P5,P95,D,B=[],[],[],[],[],[]
    for p in paths:
        a = np.asarray(Image.open(p).convert("RGB").resize((270,480)), np.float32)/255
        f = a.reshape(-1,3); mx, mn = f.max(1), f.min(1)
        sat = np.where(mx>0,(mx-mn)/np.maximum(mx,1e-6),0); l = f@np.array([.2126,.7152,.0722])
        o = np.argsort(l); k = len(o)//10
        L.append(l.mean()); S.append(sat.mean()); P5.append(np.percentile(l,5)); P95.append(np.percentile(l,95))
        D.append(f[o[:k]].mean(0)); B.append(f[o[-k:]].mean(0))
    r = lambda x: round(float(np.mean(x)),3)
    return dict(n=len(paths), luma=r(L), sat=r(S), p5=r(P5), p95=r(P95), shadow=[round(float(v),3) for v in np.mean(D,0)], hi=[round(float(v),3) for v in np.mean(B,0)])
ours = [p for p in glob.glob(sys.argv[1]+"/*.png") if not os.path.basename(p).startswith("_")]
print("ours", st(ours))
ref = glob.glob(sys.argv[2]+"/r0[235]/*.jpg")+glob.glob(sys.argv[2]+"/r06/*.jpg")+glob.glob(sys.argv[2]+"/r10/*.jpg")
print("ref day", st(ref))
