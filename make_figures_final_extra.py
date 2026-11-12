import os; os.makedirs("results/figures_final", exist_ok=True)
import json, numpy as np
import matplotlib as mpl; mpl.use("Agg")
import matplotlib.pyplot as plt
PAPER="#FFFFFF"; INK="#1C2126"; MUTE="#6B6F72"; GRID="#E3E3E3"; RUST="#C4501F"; TEAL="#1F5673"; SAND="#C9C9C9"
plt.rcParams.update({"font.family":"Carlito","font.size":18,"figure.facecolor":PAPER,"axes.facecolor":PAPER,"savefig.facecolor":PAPER,
 "axes.edgecolor":MUTE,"axes.labelcolor":MUTE,"xtick.color":MUTE,"ytick.color":MUTE,"text.color":INK,"axes.grid":True,
 "grid.color":GRID,"grid.linewidth":1,"axes.axisbelow":True,"xtick.labelsize":17,"ytick.labelsize":17,"axes.labelsize":18})
def fig(w,h): return plt.figure(figsize=(w/100,h/100),dpi=100)
def clean(ax):
    for s in ("top","right"): ax.spines[s].set_visible(False)
T="results/tables/"
# relief sweep
rows=json.load(open(T+"final_G_relief.json")); fs=sorted(set(r["f"] for r in rows))
f=fig(1040,560); ax=f.add_axes([0.09,0.15,0.89,0.76])
ax.axvspan(151,310,color=RUST,alpha=0.08,lw=0); ax.axvline(151,color=INK,lw=2)
ax.text(154,7.3,"PN16 limit 151 m",fontsize=17,fontweight="bold"); ax.text(230,-2.6,"2 pressure zones",fontsize=17,color=RUST,ha="center"); ax.text(75,-2.6,"1 pressure zone",fontsize=17,color=MUTE,ha="center")
for r in rows: ax.scatter(r["route_relief"],r["saving"],s=45,color=RUST if r["zones"]>=2 else TEAL,alpha=0.35,edgecolor="none",zorder=3)
mx=[np.mean([r["route_relief"] for r in rows if r["f"]==x]) for x in fs]; my=[np.mean([r["saving"] for r in rows if r["f"]==x]) for x in fs]
ax.plot(mx,my,color=INK,lw=2.5,marker="o",ms=8,zorder=4); ax.axhline(0,color=MUTE,lw=1)
i=fs.index(1.0); ax.annotate("real Stuttgart terrain",(mx[i],my[i]),xytext=(mx[i]-8,6.2),ha="center",fontsize=17,arrowprops=dict(arrowstyle="-",color=INK,lw=1.2))
ax.set_xlim(-5,305); ax.set_ylim(-3.5,8.2); ax.set_xlabel("height range along the pipe routes (m), Stuttgart terrain scaled 0x to 1.5x"); ax.set_ylabel("terrain saving (%)"); clean(ax)
f.savefig("results/figures_final/relief.png",dpi=200); plt.close(f)
# ILP vs greedy
G=json.load(open(T+"final_G_ilp.json"))
f=fig(1040,520); axs=f.subplots(1,2,sharey=True,gridspec_kw=dict(wspace=0.07,left=0.09,right=0.99,top=0.9,bottom=0.16))
for ax,tag,col,name in ((axs[0],"hilly",RUST,"Stuttgart"),(axs[1],"flat",TEAL,"Bremen")):
    rr=G[tag]["rows"]; k=[r["k"] for r in rr]
    ax.plot(k,[r["ilp_same_budget"] for r in rr],color=INK,lw=2.5,marker="s",ms=9,mfc=PAPER,mew=2,label="ILP optimum, same budget",zorder=3)
    ax.plot(k,[r["greedy_red"] for r in rr],color=col,lw=0,marker="o",ms=9,label="greedy",zorder=4)
    ax.set_xticks(k); ax.set_ylim(30,102); ax.set_xlabel("number of extra pipes"); ax.set_title(name,loc="left",fontsize=20,fontweight="bold",color=col,pad=8); clean(ax); ax.legend(loc="lower right",frameon=False,fontsize=16)
axs[0].set_ylabel("unserved demand removed (%)")
f.savefig("results/figures_final/ilp.png",dpi=200); plt.close(f)
# metric scatter
D=json.load(open(T+"final_G_design.json"))
f=fig(1040,520); axs=f.subplots(1,2,sharey=True,gridspec_kw=dict(wspace=0.07,left=0.09,right=0.99,top=0.9,bottom=0.16))
rr=[r for r in D if r["tag"]=="hilly"]; sty={"MST map":(SAND,"o"),"MST terrain":(INK,"s"),"Edge swap":(RUST,"^")}
for ax,key,lab in ((axs[0],"L_km","total pipe length (km)"),(axs[1],"wdist_km","demand-weighted distance to plant (km)")):
    X=[];Y=[]
    for nm,(c,m) in sty.items():
        x=[r["metrics"][nm][key] for r in rr]; y=[r["metrics"][nm]["cost"] for r in rr]; X+=x;Y+=y
        ax.scatter(x,y,s=110,color=c,marker=m,edgecolor=INK if nm=="MST map" else "none",lw=0.8,label=nm,zorder=3)
    ax.set_xlabel(lab); clean(ax); ax.set_title(f"r = {np.corrcoef(X,Y)[0,1]:+.2f}",loc="left",fontsize=20,fontweight="bold",pad=8)
axs[0].set_ylabel("cost (EUR/MWh)"); axs[0].legend(frameon=False,fontsize=16,loc="upper right")
f.savefig("results/figures_final/metric.png",dpi=200); plt.close(f)
