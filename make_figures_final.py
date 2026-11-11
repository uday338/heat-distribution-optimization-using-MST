import os; os.makedirs("results/figures_final", exist_ok=True)
import json, sys, numpy as np
import matplotlib as mpl; mpl.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, "src")
import run_final as R
import run_final_F as F
from run_final import *
from plots import hillshade

import matplotlib.font_manager as fm
FONT="Carlito" if any("Carlito" in f.name for f in fm.fontManager.ttflist) else "Liberation Sans"
PAPER="#FFFFFF"; INK="#1C2126"; MUTE="#6B6F72"; GRID="#E3E3E3"; RUST="#C4501F"; TEAL="#1F5673"; SAND="#C9C9C9"
plt.rcParams.update({"font.family":FONT,"font.size":17,"figure.facecolor":PAPER,"axes.facecolor":PAPER,"savefig.facecolor":PAPER,
 "axes.edgecolor":MUTE,"axes.labelcolor":MUTE,"xtick.color":MUTE,"ytick.color":MUTE,"text.color":INK,"axes.grid":True,
 "grid.color":GRID,"grid.linewidth":1,"axes.axisbelow":True,"axes.linewidth":1,"xtick.labelsize":17,"ytick.labelsize":17,"axes.labelsize":17})
def fig(w,h): return plt.figure(figsize=(w/100,h/100),dpi=100)
def clean(ax):
    for s in ("top","right"): ax.spines[s].set_visible(False)
def save(f,name): f.savefig(f"results/figures_final/{name}.png",dpi=200); plt.close(f)

# ---------- F1 robustness
B=json.load(open("results/tables/final_B.json"))["B_scaling"]
f=fig(1040,640); axs=f.subplots(1,2,sharey=True,gridspec_kw=dict(wspace=0.08,left=0.09,right=0.99,top=0.9,bottom=0.13))
sizes=[20,40,60,80,120,160]; rng=np.random.default_rng(1)
for ax,tag,col,name in ((axs[0],"hilly",RUST,"Stuttgart · hilly"),(axs[1],"flat",TEAL,"Bremen · flat")):
    for i,n in enumerate(sizes):
        sv=np.array([r["saving_pct"] for r in B[tag] if r["n"]==n]); seeds=[r["seed"] for r in B[tag] if r["n"]==n]
        x=i+rng.uniform(-0.16,0.16,len(sv))
        ax.scatter(x,sv,s=90,color=col,alpha=0.75,edgecolor="none",zorder=3)
        ax.plot([i-0.3,i+0.3],[np.median(sv)]*2,color=INK,lw=3,zorder=4)
        if tag=="hilly" and n==40:
            j=seeds.index(42); ax.scatter([x[j]],[sv[j]],s=330,facecolor="none",edgecolor=INK,lw=2,zorder=5)
            ax.annotate("prelim result\n+3.0 %",(x[j],sv[j]),xytext=(2.0,-5.0),fontsize=17,ha="left",va="center",
                        arrowprops=dict(arrowstyle="-",color=INK,lw=1.2,shrinkB=10))
    ax.axhline(0,color=MUTE,lw=1.2); ax.set_xticks(range(len(sizes))); ax.set_xticklabels(sizes)
    ax.set_xlabel("substations"); ax.set_title(name,loc="left",fontsize=20,fontweight="bold",color=col,pad=10); clean(ax); ax.grid(axis="x",visible=False)
axs[0].set_ylabel("cost saved by terrain weighting  (%)"); axs[0].set_ylim(-8,15)
axs[1].text(5.3,13.6,"bar = median of 10 clusterings",ha="right",fontsize=16,color=MUTE)
save(f,"robust")

# ---------- F2 pump duty over the year (Stuttgart MST-terrain)
P=R.load("hilly"); edges,nxy,ndem,nM=P["topo"]["MST-terrain"]; n=len(nxy); dem=P["dem"]
c=euro_tac(n,edges,nM,ndem,node_elevations(dem,nxy),z_route=R.route_z(dem,nxy,edges)); pe=c.detail["per_edge"]
parent,order=root_tree(n,edges,0); feed={}
for (u,v) in edges: feed[v if parent[v]==u else u]=(u,v)
paths=[]
for node in range(1,n):
    p,cur=[],node
    while cur!=0: p.append(feed[cur]); cur=parent[cur]
    paths.append(p)
def power(scale):
    dp={e:hyd.pressure_drop(pe[e]["mdot"]*scale,pe[e]["d_in"],pe[e]["L3d"],WATER.rho,WATER.mu)[0] for e in edges}
    return scale*max(sum(dp[e] for e in p) for p in paths)
q=R.duration_curve(EURO.full_load_hours/8760,0.10); hrs=np.arange(8760)
Ts=80+30*(q-0.1)/0.9; sc=q*60/(Ts-50); p1=power(1.0); idx=np.unique(np.r_[np.arange(0,300,4),np.arange(300,8760,40)]); pw=np.array([power(s) for s in sc[idx]])/p1
f=fig(900,600); ax=f.add_axes([0.11,0.14,0.86,0.80])
ax.fill_between([0,5000],[1,1],color=SAND,alpha=0.55,lw=0,zorder=1)
ax.plot([0,5000,5000],[1,1,0],color=MUTE,lw=1.5,ls=(0,(4,3)),zorder=2)
ax.fill_between(hrs[idx],pw,color=RUST,alpha=0.9,lw=0,zorder=3)
ax.plot(hrs,q,color=INK,lw=2.5,zorder=4)
ax.text(2500,0.80,"prelim assumption\n5,000 h at design power",ha="center",va="center",fontsize=17,color=INK)
ax.text(5400,0.30,"heat load",fontsize=17,color=INK)
ax.annotate("pump power actually needed",(700,0.06),xytext=(1500,0.40),fontsize=17,color=RUST,fontweight="bold",arrowprops=dict(arrowstyle="-",color=RUST,lw=1.2))
ax.set_xlim(0,8760); ax.set_ylim(0,1.05); ax.set_xlabel("hours of the year, sorted by load"); ax.set_ylabel("fraction of design value")
ax.set_xticks([0,2000,4000,6000,8760]); clean(ax); ax.grid(axis="x",visible=False)
save(f,"season"); print("pump area ratio",np.trapezoid(pw,hrs[idx])/5000)

# ---------- F3 maps + dot plot (seasonal costing)
F.ECON=__import__("dataclasses").replace(EURO,op_hours=5000*0.116,heat_price=EURO.heat_price*0.816)
FS=json.load(open("results/tables/final_F_seasonal.json"))
S=F.prep("hilly",40,42); r42=[r for r in FS if r["tag"]=="hilly" and r["seed"]==42][0]
xy=S["xy"]; d=S["dem"]; ny,nx_=d.grid.shape; ext=[d.x0,d.x0+d.step*(nx_-1),d.y0,d.y0+d.step*(ny-1)]
f=fig(1040,600); axs=f.subplots(1,2,gridspec_kw=dict(wspace=0.03,left=0.005,right=0.995,top=0.90,bottom=0.01))
eA=[tuple(e) for e in r42["mstt"]["edges"]]; eB=[tuple(e) for e in r42["ls_from_t"]["edges"]]
sA={tuple(sorted(e)) for e in eA}; sB={tuple(sorted(e)) for e in eB}
for ax,E,other,ttl in ((axs[0],eA,sB,"Terrain MST"),
                       (axs[1],eB,sA,"After flow-aware edge swaps")):
    ax.imshow(hillshade(d.grid,d.step),extent=ext,origin="lower",cmap="gray",alpha=0.30,interpolation="bilinear",zorder=0)
    ax.contourf(np.linspace(ext[0],ext[1],nx_),np.linspace(ext[2],ext[3],ny),d.grid,levels=8,cmap="YlOrBr",alpha=0.28,zorder=1)
    per=F.tac(S,E).detail["per_edge"]; dn=np.array([per[e]["dn"] for e in E],float)
    for e,w in zip(E,1.5+7*np.sqrt((dn-dn.min())/(dn.max()-dn.min()))):
        diff=tuple(sorted(e)) not in other
        ax.plot(xy[list(e),0],xy[list(e),1],color=RUST if diff else INK,lw=w,solid_capstyle="round",zorder=3)
    ax.scatter(xy[1:,0],xy[1:,1],s=42,c=PAPER,edgecolors=INK,linewidths=1.2,zorder=5)
    ax.scatter(xy[0,0],xy[0,1],s=420,marker="*",c=RUST,edgecolors=PAPER,linewidths=1.5,zorder=6)
    ax.set_xlim(xy[:,0].min()-350,xy[:,0].max()+350); ax.set_ylim(xy[:,1].min()-350,xy[:,1].max()+350)
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
    for s in ax.spines.values(): s.set_visible(False)
    ax.set_title(ttl,loc="left",fontsize=18,fontweight="bold",pad=10)
save(f,"maps")

f=fig(600,600); ax=f.add_axes([0.16,0.13,0.82,0.80]); rng=np.random.default_rng(3)
xs=0
for tag,col in (("hilly",RUST),("flat",TEAL)):
    rr=[r for r in FS if r["tag"]==tag]
    for k,lab in (("mst2d","MST\nmap"),("mstt","MST\nterrain"),("ls_from_t","edge\nswap")):
        v=np.array([r[k]["specific"] for r in rr]); ax.scatter(xs+rng.uniform(-0.15,0.15,10),v,s=80,color=col,alpha=0.75,edgecolor="none",zorder=3)
        ax.plot([xs-0.3,xs+0.3],[np.median(v)]*2,color=INK,lw=3,zorder=4); xs+=1
    xs+=0.5
ax.set_xticks([0,1,2,3.5,4.5,5.5]); ax.set_xticklabels(["MST\nmap","MST\nterrain","edge\nswap"]*2,fontsize=15)
ax.text(1,20.1,"Stuttgart",ha="center",color=RUST,fontweight="bold",fontsize=18); ax.text(4.5,20.1,"Bremen",ha="center",color=TEAL,fontweight="bold",fontsize=18)
ax.set_ylim(11,20.8); ax.set_ylabel("total annual cost  (EUR/MWh)"); clean(ax); ax.grid(axis="x",visible=False)
save(f,"dots")

# ---------- F4 pressure
f=fig(1040,430); ax=f.add_axes([0.13,0.2,0.85,0.62]); rng=np.random.default_rng(5)
for y,tag,col in ((1,"hilly",RUST),(0,"flat",TEAL)):
    v=np.array([r["route_relief_t"] for r in B[tag]]); ax.scatter(v,y+rng.uniform(-0.16,0.16,len(v)),s=70,color=col,alpha=0.6,edgecolor="none",zorder=3)
for lim,lab in ((87,"PN10"),(151,"PN16"),(247,"PN25")):
    ax.axvline(lim,color=INK,lw=2 if lab=="PN16" else 1.3,ls="-" if lab=="PN16" else (0,(4,3)),zorder=2)
    ax.text(lim,1.62,f"{lab}\n{lim} m",ha="center",va="bottom",fontsize=16,fontweight="bold" if lab=="PN16" else "normal")
ax.set_yticks([0,1]); ax.set_yticklabels(["Bremen","Stuttgart"],fontsize=18); ax.set_ylim(-0.5,1.55); ax.set_xlim(0,270)
ax.set_xlabel("relief along the built pipe routes (m)"); clean(ax); ax.grid(axis="y",visible=False)
save(f,"pressure")

# ---------- F5 exact vs greedy
C=json.load(open("results/tables/final_C.json"))["C_exact"]
f=fig(1040,600); axs=f.subplots(1,2,sharey=True,gridspec_kw=dict(wspace=0.07,left=0.09,right=0.99,top=0.9,bottom=0.14))
for ax,tag,col,name in ((axs[0],"hilly",RUST,"Stuttgart"),(axs[1],"flat",TEAL,"Bremen")):
    fr=C[tag]["frontier"]["3"]; x=np.array(fr["cost"]); y=np.array(fr["eud_red"])
    ax.step(np.r_[0,x,40],np.r_[0,y,y[-1]],where="post",color=INK,lw=2.2,zorder=2)
    g=C[tag]["greedy"]; ax.scatter([a["cost"] for a in g[:3]],[a["eud_red"] for a in g[:3]],s=260,color=col,edgecolor=PAPER,lw=2,zorder=4)
    for a in g[:3]: ax.annotate(f"{a['k']}",(a["cost"],a["eud_red"]),ha="center",va="center",color=PAPER,fontsize=15,fontweight="bold",zorder=5)
    ax.set_xlim(0,30); ax.set_ylim(0,102); ax.set_xlabel("cost of extra pipes (% of network)")
    ax.set_title(name,loc="left",fontsize=20,fontweight="bold",color=col,pad=10); clean(ax)
axs[0].set_ylabel("expected unserved demand removed  (%)")
axs[0].text(29.5,8,"line: best possible with ≤ 3 pipes\n(all 79 million combinations)\ndots: greedy after 1, 2, 3 pipes",ha="right",fontsize=16,color=MUTE)
save(f,"exact")

# ---------- trimmed copy of the map figure used in the slides
from PIL import Image, ImageChops
im = Image.open("results/figures_final/maps.png").convert("RGB")
bb = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).getbbox()
im.crop((bb[0] - 10, bb[1] - 10, bb[2] + 10, bb[3] + 10)).save("results/figures_final/maps_c.png")
