(function(){
const root=document.getElementById("sys");
const $=s=>root.querySelector(s);
let HOME="";
const fetch=(u,o={})=>window.fetch(u,{...o,headers:{...(o.headers||{}),"X-Manager":"1"}});
const gb=b=>(b/1e9).toFixed(1)+" GB",mb=b=>b>=1e9?gb(b):Math.round(b/1e6)+" MB";
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const toast=t=>{const e=$("#toast");e.textContent=t;e.style.display="block";clearTimeout(e.t);e.t=setTimeout(()=>e.style.display="none",5000)};
const ask2=m=>new Promise(res=>{const back=document.activeElement,bg=[$(".sysbody")];
 $("#dlgmsg").textContent=m;$("#dlg").style.display="flex";bg.forEach(e=>e.inert=true);$("#dno").focus();
 const done=v=>{$("#dlg").style.display="none";bg.forEach(e=>e.inert=false);$("#dlg").onkeydown=null;back&&back.focus&&back.focus();res(v)};
 $("#dyes").onclick=()=>done(true);$("#dno").onclick=()=>done(false);
 $("#dlg").onkeydown=e=>{if(e.key=="Escape"){e.stopPropagation();done(false)}if(e.key=="Tab"){const f=[$("#dno"),$("#dyes")],i=f.indexOf(document.activeElement);e.preventDefault();f[(i+(e.shiftKey?-1:1)+2)%2].focus()}}});
const post=(u,b)=>fetch(u,{method:"POST",body:JSON.stringify(b)}).then(r=>r.json());
root.querySelectorAll("nav button").forEach(b=>b.onclick=()=>{
 root.querySelectorAll("nav button").forEach(x=>{x.classList.toggle("on",x==b);x.setAttribute("aria-selected",x==b);x.tabIndex=x==b?0:-1});
 root.querySelectorAll("main>section").forEach(s=>s.classList.toggle("hidden",s.id!=b.dataset.t));
 if(b.dataset.t=="files"&&!window.filesLoaded)loadDir("");if(b.dataset.t=="apps"&&!window.appsLoaded)loadApps();if(b.dataset.t=="brew"&&!window.brewLoaded)loadBrew();if(b.dataset.t=="dev")loadDev();});
$("nav").onkeydown=e=>{const t=[...root.querySelectorAll("nav button")],i=t.indexOf(document.activeElement);
 if(i<0||!["ArrowRight","ArrowLeft","Home","End"].includes(e.key))return;e.preventDefault();
 const n=e.key=="Home"?0:e.key=="End"?t.length-1:(i+(e.key=="ArrowRight"?1:-1)+t.length)%t.length;t[n].focus();t[n].click()};

const beam=(id,on)=>$("#"+id).classList.toggle("on",on);
const reduce=matchMedia("(prefers-reduced-motion: reduce)").matches;
const ring=(p,c)=>`<svg class="ring" viewBox="0 0 84 84" aria-hidden="true"><circle class="rt" cx="42" cy="42" r="36"/><circle class="rv" cx="42" cy="42" r="36" style="stroke:${c};stroke-dasharray:226.2;stroke-dashoffset:${first&&!reduce?226.2:226.2*(1-p)}" data-off="${226.2*(1-p)}"/><text class="rp" x="42" y="48" text-anchor="middle">${Math.round(p*100)}%</text></svg>`;
function countUp(){if(reduce)return;root.querySelectorAll(".cu").forEach(el=>{const to=+el.dataset.to,t0=performance.now();
 const f=t=>{const k=Math.min((t-t0)/900,1),e=1-Math.pow(1-k,4);el.textContent=(to*e).toFixed(1);if(k<1)requestAnimationFrame(f)};requestAnimationFrame(f)})}
let first=true,histFirst=true;
async function drawHist(){let d;try{d=await fetch("/api/mgr/history").then(r=>r.json())}catch(e){return}
 const svg=$("#hist"),W=Math.max(svg.clientWidth,300),Ht=150,L=30,B=18,win=1800,now=Date.now()/1000,pts=d.filter(p=>now-p.t<=win);
 svg.setAttribute("viewBox",`0 0 ${W} ${Ht}`);
 if(pts.length<2){svg.innerHTML=`<text x="${W/2}" y="${Ht/2}" text-anchor="middle" style="font-size:12px">Collecting readings… the chart fills in every 5 seconds.</text>`;return}
 const x=t=>L+(1-(now-t)/win)*(W-L-4),y=v=>4+(1-Math.min(v,1))*(Ht-B-8);
 const path=k=>pts.map((p,i)=>(i?"L":"M")+x(p.t).toFixed(1)+" "+y(p[k]).toFixed(1)).join(" ");
 const area=k=>path(k)+` L${x(pts[pts.length-1].t).toFixed(1)} ${y(0)} L${x(pts[0].t).toFixed(1)} ${y(0)} Z`;
 const grid=[0,.5,1].map(v=>`<line class="gl" x1="${L}" x2="${W-4}" y1="${y(v)}" y2="${y(v)}"/><text x="${L-5}" y="${y(v)+3}" text-anchor="end">${v*100}%</text>`).join("");
 const C={mem:"var(--acc)",swap:"var(--warn)",cpu:"var(--ok)"};
 svg.innerHTML=grid+`<g class="${histFirst?"":"slide"}">`+["swap","cpu","mem"].map(k=>`<path class="ar" d="${area(k)}" fill="${C[k]}"/><path class="ln" data-k="${k}" d="${path(k)}" stroke="${C[k]}"/>`).join("")+`</g><text x="${L}" y="${Ht-3}">30 min ago</text><text x="${W-4}" y="${Ht-3}" text-anchor="end">now</text>`;
 const l=pts[pts.length-1],pc=v=>Math.round(v*100)+"%";
 $("#histnow").textContent=`Now: memory ${pc(l.mem)} · swap ${pc(l.swap)} · CPU ${pc(l.cpu)}`;
 svg.setAttribute("aria-label",`History for the last 30 minutes. Now: memory ${pc(l.mem)}, swap ${pc(l.swap)}, CPU load ${pc(l.cpu)}.`);
 if(histFirst&&!reduce){svg.querySelectorAll(".ln").forEach(p=>{const n=p.getTotalLength();p.style.transition="none";p.style.strokeDasharray=n;p.style.strokeDashoffset=n;
  requestAnimationFrame(()=>requestAnimationFrame(()=>{p.style.transition="stroke-dashoffset 1.4s cubic-bezier(.16,1,.3,1)";p.style.strokeDashoffset=0}))})}
 histFirst=false}
async function loadDev(){
 let d;try{d=await fetch("/api/mgr/devices").then(r=>r.json())}catch(e){$("#devnet").innerHTML='<div class="card"><div class="sub">Can\u2019t reach the manager.</div></div>';return}
 const n=d.network||{},w=n.wifi||{},row=(k,v)=>v==null||v===""?"":`<div class="sub"><b>${esc(k)}</b> ${esc(v)}</div>`;
 const online=n.online?`<span style="color:var(--ok)">\u25CF Online</span>`:`<span style="color:var(--bad)">\u25CB Offline</span>`;
 $("#devnet").innerHTML=`<div class="card"><h2>Internet</h2><div class="big">${online}</div>${row("Latency",n.latency_ms!=null?n.latency_ms.toFixed(0)+" ms":"")}${row("Via",n.interface)}${row("Router",n.gateway)}${row("DNS",(n.dns||[]).join(", "))}</div>`
  +`<div class="card"><h2>Wi\u2011Fi</h2>${w.channel?`<div class="big">${esc(w.signal||"")}</div>${row("Channel",w.channel)}${row("Standard",w.mode)}${row("Speed",w.rate?w.rate+" Mbps":"")}${row("Security",w.security)}`:`<div class="sub">${(n.ports||[]).some(p=>p.port=="Wi-Fi"&&p.ip)?"Reading Wi\u2011Fi details\u2026 (first load takes ~15 s)":"Not connected"}</div>`}</div>`
  +`<div class="card"><h2>Network ports</h2>${(n.ports||[]).map(p=>`<div class="sub"><b>${esc(p.port)}</b> ${esc(p.device)} \u00B7 ${p.ip?esc(p.ip):"no address"}</div>`).join("")||'<div class="sub">None</div>'}</div>`;
 const dr=d.drives||[];
 $("#devdrives").innerHTML=dr.length?dr.map(v=>{const used=v.total-v.free,pc=v.total?used/v.total:0;
  return `<div style="margin-bottom:14px"><div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><div><b>${esc(v.name)}</b> <span class="sub">${v.external?"External":"Internal"}${v.protocol?" \u00B7 "+esc(v.protocol):""} \u00B7 ${esc(v.fs||"")}${v.writable?"":" \u00B7 read\u2011only"}</span></div>${v.external&&v.ejectable?`<button class="act" data-eject="${esc(v.mount)}">Eject</button>`:""}</div>
  <div class="bar" role="img" aria-label="${esc(v.name)} ${Math.round(pc*100)}% used"><i style="width:${pc*100}%;background:${pc>.9?"var(--bad)":"var(--acc)"}"></i></div>
  <div class="sub">${gb(used)} used \u00B7 ${gb(v.free)} free of ${gb(v.total)} \u00B7 ${esc(v.device||"")} \u00B7 ${esc(v.mount)}</div></div>`}).join(""):'<div class="sub">No drives found</div>';
 $("#devdrives").querySelectorAll("[data-eject]").forEach(b=>b.onclick=async()=>{if(!await ask2("Eject "+b.dataset.eject.split("/").pop()+"?"))return;
  const r=await post("/api/mgr/eject",{mount:b.dataset.eject});toast(r.ok?"Ejected.":r.message||"Couldn\u2019t eject.");loadDev()});
 const bt=d.bluetooth||{},us=d.usb||[];
 $("#devother").innerHTML=`<div class="card"><h2>Bluetooth</h2><div class="big">${bt.on==null?"n/a":bt.on?"On":"Off"}</div>${(bt.connected||[]).map(x=>row(x.name,[x.type,x.battery].filter(Boolean).join(" \u00B7 "))).join("")||'<div class="sub">No devices connected</div>'}</div>`
  +`<div class="card"><h2>USB devices</h2>${us.map(x=>row(x.name,[x.vendor,x.speed].filter(Boolean).join(" \u00B7 "))).join("")||'<div class="sub">None connected</div>'}</div>`}
async function loadTrash(){
 const t=await fetch("/api/mgr/trash-info").then(r=>r.json());
 $("#trashinfo").textContent=t.count==null?"Couldn't read the Trash":t.count==0?"Trash is empty":`${t.count} item(s)`+(t.size?` · about ${mb(t.size)}`:"");
 $("#emptytrash").disabled=!t.count}
$("#emptytrash").onclick=async()=>{if(!await ask2("Permanently delete everything in the Trash? This cannot be undone."))return;
 toast("Emptying Trash…");const r=await post("/api/mgr/empty-trash",{});toast(r.message);loadTrash();loadSys()};
function swapHtml(s){const v=k=>{const x=(s||"").match(new RegExp(k+" = ([\\d.]+)M"));return x?+x[1]*1048576:null},u=v("used"),t=v("total");
 return u==null?`<div class="big">n/a</div>`:`<div class="big">${gb(u)} <span class="sub">of ${gb(t)} used</span></div><div class="bar" role="img" aria-label="Swap ${Math.round(u/t*100)}% used"><i style="width:${u/t*100}%;background:var(--warn)"></i></div>`}
async function loadSys(){
 let s;try{s=await fetch("/api/mgr/system").then(r=>r.json())}catch(e){$("#cards").innerHTML='<div class="card"><div class="sub">Can\u2019t reach the manager. Is manager.py still running?</div></div>';return}
 const m=s.memory,pct=x=>(x/m.total*100)+"%";
 const pressure=m.used/m.total;
 $("#cards").innerHTML=`
 <div class="card"><h2>Memory</h2><div class="gwrap">${ring(m.used/m.total,pressure>.9?"var(--bad)":"var(--acc)")}<div><div class="big"><span class="cu" data-to="${(m.used/1e9).toFixed(1)}">${(m.used/1e9).toFixed(1)}</span> GB <span class="sub">of ${gb(m.total)}</span></div>
  <div class="bar" role="img" aria-label="Memory breakdown: wired ${gb(m.wired)}, active ${gb(m.active)}, compressed ${gb(m.compressed)}"><i style="width:${pct(m.wired)};background:var(--bad)"></i><i style="width:${pct(m.active)};background:var(--acc)"></i><i style="width:${pct(m.compressed)};background:var(--warn)"></i></div>
  <div class="sub"><span class="dot" style="background:var(--bad)"></span>Wired ${gb(m.wired)}<span class="dot" style="background:var(--acc)"></span>Active ${gb(m.active)}<span class="dot" style="background:var(--warn)"></span>Compressed ${gb(m.compressed)}<span class="dot" style="background:var(--line)"></span>Free ${gb(m.free)}</div></div></div></div>
 <div class="card"><h2>Swap</h2>${swapHtml(m.swap)}<div class="sub">${pressure>.9?"High memory use: consider quitting heavy apps":"Memory looks healthy"}</div></div>
 <div class="card"><h2>Disk</h2><div class="gwrap">${ring(s.disk.used/s.disk.total,s.disk.free/s.disk.total<.1?"var(--bad)":"var(--acc)")}<div><div class="big"><span class="cu" data-to="${(s.disk.free/1e9).toFixed(1)}">${(s.disk.free/1e9).toFixed(1)}</span> GB <span class="sub">free of ${gb(s.disk.total)}</span></div>
  <div class="bar" role="img" aria-label="Disk ${Math.round(s.disk.used/s.disk.total*100)}% used"><i style="width:${s.disk.used/s.disk.total*100}%;background:${s.disk.free/s.disk.total<.1?"var(--bad)":"var(--acc)"}"></i></div><div class="sub">${gb(s.disk.used)} used${s.disk.free/s.disk.total<.1?" · low on space":""}</div></div></div></div>
 <div class="card"><h2>CPU load</h2><div class="gwrap">${ring(Math.min(s.load[0]/s.cpus,1),s.load[0]/s.cpus>.9?"var(--bad)":"var(--acc)")}<div><div class="big">${s.load[0].toFixed(2)}</div><div class="sub">${s.cpus} cores · 5m ${s.load[1].toFixed(2)} · 15m ${s.load[2].toFixed(2)}</div></div></div></div>`;
 drawHist();
 {const d=root.querySelector(".live i");d.classList.remove("tick");void d.offsetWidth;d.classList.add("tick")}
 if(first){requestAnimationFrame(()=>requestAnimationFrame(()=>root.querySelectorAll(".rv[data-off]").forEach(c=>c.style.strokeDashoffset=c.dataset.off)));countUp();first=false}
 $("#procs").innerHTML="<tr><th>Process</th><th class=n>Memory</th><th class=n>CPU %</th><th></th></tr>"+s.procs.map(p=>
  `<tr><td>${esc(p.name)} <span class=sub>${p.pid}</span></td><td class=n>${mb(p.rss)}</td><td class=n>${p.cpu.toFixed(1)}</td>
  <td class=n>${p.user==s.me?`<button class=act data-pid=${p.pid} data-n="${esc(p.name)}">Quit</button>`:""}</td></tr>`).join("");
}
$("#procs").onclick=async e=>{const b=e.target.closest("[data-pid]");if(!b||!await ask2(`Quit ${b.dataset.n}? Unsaved work in it may be lost.`))return;
 const r=await post("/api/mgr/quit",{pid:+b.dataset.pid});toast(r.message);setTimeout(loadSys,800)};

let apps=[];
async function loadApps(refresh){
 $("#applist").innerHTML="<tr><td>Scanning apps (sizes and last-used dates)…</td></tr>";beam("abeam",true);
 apps=await fetch("/api/mgr/apps"+(refresh?"?refresh=1":"")).then(r=>r.json());window.appsLoaded=true;beam("abeam",false);renderApps()}
function renderApps(){
 const q=$("#q").value.toLowerCase(),cut=new Date(Date.now()-182*864e5).toISOString().slice(0,10);
 $("#applist").innerHTML="<tr><th>App</th><th>Version</th><th>Last used</th><th class=n>Size</th><th></th></tr>"+
 apps.filter(a=>a.name.toLowerCase().includes(q)).map(a=>{const stale=!a.lastUsed||a.lastUsed<cut;
  return `<tr><td>${esc(a.name)}${a.appStore?'<span class=tag>App Store</span>':""}</td><td>${esc(a.version)}</td>
  <td>${a.lastUsed||"never/unknown"}${stale?'<span class="tag stale">unused</span>':""}</td><td class=n>${mb(a.size)}</td>
  <td class=n><button class=act data-path="${esc(a.path)}" data-n="${esc(a.name)}">Uninstall</button></td></tr>`}).join("")}
$("#q").oninput=renderApps;$("#rescan").onclick=()=>loadApps(true);
$("#applist").onclick=async e=>{const b=e.target.closest("[data-path]");if(!b||!await ask2(`Move ${b.dataset.n} to the Trash?`))return;
 const r=await post("/api/mgr/trash",{path:b.dataset.path});toast(r.message);if(r.ok){loadApps(true);loadTrash()}};

async function loadBrew(){
 const d=await fetch("/api/mgr/brew").then(r=>r.json());window.brewLoaded=true;
 fetch("/api/mgr/brew-outdated").then(r=>r.json()).then(o=>{d.outdated=o.outdated;if(o.outdated.length)paintBrew(d)}).catch(()=>{});
 paintBrew(d)}
function paintBrew(d){
 if(!d.installed){$("#brewlist").innerHTML="<tr><td>Homebrew isn't installed.</td></tr>";return}
 $("#brewlist").innerHTML="<tr><th>Package</th><th>Type</th><th>Version</th><th></th></tr>"+d.items.map(p=>
  `<tr><td>${esc(p.name)}${d.outdated.includes(p.name)?'<span class="tag stale">outdated</span>':""}</td><td>${p.kind}</td><td>${esc(p.version)}</td>
  <td class=n><button class=act data-name="${esc(p.name)}" data-kind=${p.kind}>Uninstall</button></td></tr>`).join("")}
$("#brewlist").onclick=async e=>{const b=e.target.closest("[data-name]");if(!b||!await ask2(`brew uninstall ${b.dataset.name}? This is permanent.`))return;
 toast("Uninstalling…");const r=await post("/api/mgr/brew-uninstall",{name:b.dataset.name,kind:b.dataset.kind});toast(r.ok?"Uninstalled "+b.dataset.name:r.message);if(r.ok)loadBrew()};

let fdata={entries:[]},fsel=new Set(),fview=[];
async function loadDir(path,large){
 $("#flist").innerHTML="<tr><td>Scanning… folder sizes can take a few seconds.</td></tr>";fsel.clear();beam("fbeam",true);
 const r=await fetch(large?"/api/mgr/dir?large="+large:"/api/mgr/dir?path="+encodeURIComponent(path||"")).then(r=>r.json());
 beam("fbeam",false);
 if(r.error){$("#flist").innerHTML=`<tr><td>${esc(r.error)}</td></tr>`;return}
 fdata=r;window.filesLoaded=true;fillSizes(r);$("#fsort").value=large?"size":$("#fsort").value;renderFiles()}
let sizeGen=0;
async function fillSizes(r){const gen=++sizeGen,todo=r.entries.filter(e=>e.dir&&e.size==null);let n=0;
 const work=async()=>{while(todo.length&&gen==sizeGen){const e=todo.shift();
   try{const s=await fetch("/api/mgr/dirsize?path="+encodeURIComponent(e.path)).then(x=>x.json());e.size=s.size==null?-1:s.size}catch(x){e.size=-1}
   if(gen==sizeGen)n++}};
 await Promise.all([work(),work(),work()]);if(gen==sizeGen&&n)renderFiles()}
function renderFiles(){
 const q=$("#fq").value.toLowerCase(),t=$("#ftype").value,min=+$("#fmin").value,age=+$("#fage").value,sort=$("#fsort").value,now=Date.now()/1000;
 fview=fdata.entries.filter(e=>e.name.toLowerCase().includes(q)&&(!t||(t=="d")==e.dir)&&(e.size||0)>=min&&(!age||now-e.mtime>age*86400));
 fview.sort((a,b)=>sort=="name"?a.name.localeCompare(b.name):sort=="date"?a.mtime-b.mtime:(b.size||0)-(a.size||0));
 $("#fpath").textContent=fdata.path;$("#fup").disabled=!fdata.parent;
 $("#flist").innerHTML="<tr><th></th><th>Name</th><th>Modified</th><th class=n>Size</th></tr>"+fview.map((e,i)=>
  `<tr><td style="width:28px">${e.protected?"":`<input type=checkbox aria-label="Select ${esc(e.name)}" data-i=${i} ${fsel.has(e.path)?"checked":""}>`}</td>
  <td>${e.dir?`<a href="#" data-open=${i}><svg class=ico viewBox="0 0 16 16" aria-hidden="true"><path d="M1.5 4.5a1 1 0 0 1 1-1h3.2l1.5 1.5h6.3a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1z"/></svg>${esc(e.name)}</a>`:`<a href="#" data-show=${i} title="Show in Finder">${esc(e.name)}</a><a class=lnk data-up=${i}>Open folder</a>`}${e.protected?'<span class=tag>protected</span>':""}${!e.dir&&fdata.path.startsWith("Files")?`<div class=sub>${esc(e.path)}</div>`:""}</td>
  <td>${new Date(e.mtime*1000).toISOString().slice(0,10)}</td><td class=n>${e.size==null?"calculating…":e.size<0?"n/a":mb(e.size)}</td></tr>`).join("")||"<tr><td>No matching items.</td></tr>";
 updSel()}
function updSel(){const sz=[...fsel].reduce((s,p)=>s+Math.max(0,(fdata.entries.find(e=>e.path==p)||{}).size||0),0);
 $("#fsel").textContent=fsel.size?`${fsel.size} selected · ${mb(sz)}`:"";$("#fdel").disabled=!fsel.size}
$("#flist").onclick=async e=>{const sh=e.target.closest("[data-show]"),up=e.target.closest("[data-up]");
 if(sh){e.preventDefault();const r=await post("/api/mgr/reveal",{path:fview[+sh.dataset.show].path});if(!r.ok)toast(r.message);return}
 if(up){loadDir(fview[+up.dataset.up].path.replace(/\/[^\/]*$/,""));return}
 const o=e.target.closest("[data-open]");if(o){e.preventDefault();loadDir(fview[+o.dataset.open].path);return}
 const c=e.target.closest("[data-i]");if(c){const p=fview[+c.dataset.i].path;c.checked?fsel.add(p):fsel.delete(p);updSel()}};
["#fq","#ftype","#fsort","#fmin","#fage"].forEach(s=>$(s).oninput=renderFiles);
$("#fup").onclick=()=>fdata.parent&&loadDir(fdata.parent);
root.querySelectorAll("[data-go]").forEach(b=>b.onclick=()=>{const g=b.dataset.go;
 g=="large"?loadDir("",100):loadDir(g=="home"?"":HOME+"/"+g)});
$("#fdel").onclick=async()=>{const n=fsel.size;if(!await ask2(`Move ${n} selected item(s) to the Trash?`))return;
 const r=await post("/api/mgr/trash-paths",{paths:[...fsel]});toast(r.message);loadTrash();
 const isLarge=fdata.path.startsWith("Files");isLarge?loadDir("",parseInt(fdata.path.match(/\d+/)[0])):loadDir(fdata.path)};

let dgroups=[];
$("#dgo").onclick=async()=>{
 const base=$("#dpath").value,root=base?HOME+"/"+base:"";
 $("#dres").innerHTML="";$("#dgo").disabled=true;beam("dbeam",true);$("#dstat").textContent="Starting scan…";
 const s=await post("/api/mgr/dupes-start",{path:root,min_mb:$("#dmin").value});
 if(!s.id){$("#dstat").textContent=s.message;$("#dgo").disabled=false;beam("dbeam",false);return}
 for(;;){await new Promise(r=>setTimeout(r,1500));
  const j=await fetch("/api/mgr/dupes-status?id="+s.id).then(r=>r.json());
  if(j.stage!="done"){$("#dstat").textContent=j.stage+(j.stage=="Scanning files"?` · ${j.scanned} files seen`:` · ${j.progress||0}%`);continue}
  $("#dgo").disabled=false;beam("dbeam",false);
  if(j.error){$("#dstat").textContent="Error: "+j.error;return}
  dgroups=j.result.groups;renderDupes(j.result);return}};
function renderDupes(r){
 if(!dgroups.length){$("#dstat").textContent="No duplicate files found.";$("#dres").innerHTML="";return}
 $("#dstat").textContent=`${dgroups.length}${r.truncated?"+":""} groups · about ${mb(r.reclaimable)} can be freed. In each group the radio marks the copy to KEEP (oldest by default); the other copies are moved to the Trash.`;
 $("#dres").innerHTML=dgroups.map((g,gi)=>`<div class="grp"><div style="display:flex;justify-content:space-between;gap:8px"><b>${g.files.length} copies · ${mb(g.size)} each</b>
  <label class=sub><input type=checkbox data-skip=${gi}> Skip group</label></div>`+
  g.files.map((f,fi)=>`<label><input type=radio aria-label="Keep this copy" name="g${gi}" data-g=${gi} data-f=${fi} ${fi==0?"checked":""}><span style="word-break:break-all">${esc(f.path.replace(HOME,"~"))}
   <span class=sub>${new Date(f.mtime*1000).toISOString().slice(0,10)}</span><a class=lnk data-rev="${gi}:${fi}">Show in Finder</a><a class=lnk data-dir="${gi}:${fi}">Open folder</a></span></label>`).join("")+`</div>`).join("")+
  `<button class="send" id="dtrash">Move duplicates to Trash</button> <span class=sub id="dcount"></span>`;
 updD()}
function dupeItems(){const items=[];dgroups.forEach((g,gi)=>{
  if(root.querySelector(`[data-skip="${gi}"]`).checked)return;
  const k=root.querySelector(`input[name=g${gi}]:checked`),ki=+k.dataset.f;
  g.files.forEach((f,fi)=>{if(fi!=ki)items.push({path:f.path,keep:g.files[ki].path,size:g.size})})});return items}
function updD(){const it=dupeItems(),c=$("#dcount");if(c)c.textContent=`${it.length} file(s) · ${mb(it.reduce((s,x)=>s+x.size,0))}`;const b=$("#dtrash");if(b)b.disabled=!it.length}
$("#dres").onchange=updD;
$("#dres").onclick=async e=>{
 const rv=e.target.closest("[data-rev]"),dr=e.target.closest("[data-dir]");
 if(rv){e.preventDefault();const [g,f]=rv.dataset.rev.split(":");const r=await post("/api/mgr/reveal",{path:dgroups[g].files[f].path});if(!r.ok)toast(r.message);return}
 if(dr){e.preventDefault();const [g,f]=dr.dataset.dir.split(":");loadDir(dgroups[g].files[f].path.replace(/\/[^\/]*$/,""));return}
 if(e.target.id=="dtrash"){const it=dupeItems();if(!await ask2(`Move ${it.length} duplicate file(s) (${mb(it.reduce((s,x)=>s+x.size,0))}) to the Trash? One copy of each stays.`))return;
  toast("Moving to Trash…");const r=await post("/api/mgr/trash-dupes",{items:it});toast(r.message);loadTrash();$("#dgo").click()}};
let started=false;
async function start(){if(started)return;started=true;
 try{HOME=(await fetch("/api/mgr/info").then(r=>r.json())).home}catch(e){started=false;return}
 loadSys();loadTrash()}
setInterval(()=>{if(started&&!document.hidden&&!root.classList.contains("hidden")&&!$("#dev").classList.contains("hidden"))loadDev()},8000);
setInterval(()=>{if(started&&!document.hidden&&!root.classList.contains("hidden")&&!$("#mem").classList.contains("hidden"))loadSys()},5000);
const sysBtn=document.getElementById("sysBtn");
function openSys(){window.__orbPaused=true;root.classList.remove("hidden");start();if(started)loadTrash();$('[role=tab][aria-selected=true]').focus()}
function closeSys(){if(window.__standalone)return;window.__orbPaused=false;root.classList.add("hidden");sysBtn.focus()}
sysBtn.onclick=openSys;$("#sysClose").onclick=closeSys;
root.addEventListener("keydown",e=>{if(e.key==="Escape"){e.stopPropagation();closeSys()}});
if(window.__standalone||location.hash==="#system")openSys();   // the standalone AI Manager app opens straight to this panel
})();
