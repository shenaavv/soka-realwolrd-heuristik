const $ = id => document.getElementById(id);
let showAllLogs = true, latestLogs = [];
const num = (v, digits=2) => v === undefined || v === null || v === '' ? '—' : Number(v).toLocaleString('en-US',{maximumFractionDigits:digits});
const seconds = v => v === undefined || v === null ? '—' : `${num(v,3)} s`;
function setText(id,value){$(id).textContent=value;}
function renderBars(loads){
  const entries=Object.entries(loads||{}); const max=Math.max(1,...entries.map(x=>Number(x[1])));
  $('vm-chart').innerHTML=entries.length?entries.map(([vm,load])=>`<div class="bar-row"><span>${vm}</span><div class="bar-track"><div class="bar-fill" style="width:${Math.max(1,Number(load)/max*100)}%"></div></div><span class="bar-value">${num(load,2)} s</span></div>`).join(''):'<div class="muted">No VM load data</div>';
}
const chartColors=['#2878d0','#18a477','#e2a63b','#8b72cf','#d86b78','#36a6a6'];
function prepareCanvas(id){
 const canvas=$(id); if(!canvas) return null;
 const rect=canvas.getBoundingClientRect(); if(!rect.width||!rect.height) return null;
 const ratio=window.devicePixelRatio||1; canvas.width=Math.round(rect.width*ratio);canvas.height=Math.round(rect.height*ratio);
 const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,rect.width,rect.height);
 return {ctx,w:rect.width,h:rect.height};
}
function drawLoadChart(loads){
 const c=prepareCanvas('load-chart');if(!c)return;const entries=Object.entries(loads||{});const {ctx,w,h}=c;
 if(!entries.length){ctx.fillStyle='#8a98a9';ctx.font='12px sans-serif';ctx.fillText('Belum ada data beban VM',12,24);return;}
 const left=48,right=14,top=14,bottom=42,plotH=h-top-bottom,plotW=w-left-right,max=Math.max(1,...entries.map(x=>Number(x[1])||0));
 ctx.strokeStyle='#e8edf3';ctx.fillStyle='#8492a3';ctx.font='10px sans-serif';ctx.textAlign='right';
 for(let i=0;i<=4;i++){const y=top+plotH*i/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-right,y);ctx.stroke();ctx.fillText((max*(1-i/4)).toFixed(1),left-8,y+3);}
 const slot=plotW/entries.length,bw=Math.min(54,slot*.55);
 entries.forEach(([vm,value],i)=>{const v=Math.max(0,Number(value)||0),bh=v/max*(plotH-3),x=left+i*slot+(slot-bw)/2,y=top+plotH-bh;ctx.fillStyle=chartColors[i%chartColors.length];ctx.beginPath();ctx.roundRect(x,y,bw,bh,5);ctx.fill();ctx.fillStyle='#53657a';ctx.textAlign='center';ctx.font='10px sans-serif';ctx.fillText(vm,x+bw/2,h-18);ctx.fillStyle='#34465b';ctx.font='10px sans-serif';ctx.fillText(v.toFixed(2),x+bw/2,Math.max(11,y-6));});
}
function drawDistributionChart(assignments){
 const c=prepareCanvas('distribution-chart');if(!c)return;const {ctx,w,h}=c;const counts={};(assignments||[]).forEach(a=>{const key=a.vm||'Unknown';counts[key]=(counts[key]||0)+1;});const entries=Object.entries(counts);const total=entries.reduce((sum,x)=>sum+x[1],0);
 if(!total){ctx.fillStyle='#8a98a9';ctx.font='12px sans-serif';ctx.fillText('Belum ada data task',12,24);$('distribution-legend').innerHTML='';return;}
 const radius=Math.min(w*.27,h*.43),cx=w/2,cy=h/2;let angle=-Math.PI/2;
 entries.forEach(([vm,count],i)=>{const next=angle+(count/total)*Math.PI*2;ctx.beginPath();ctx.moveTo(cx,cy);ctx.arc(cx,cy,radius,angle,next);ctx.closePath();ctx.fillStyle=chartColors[i%chartColors.length];ctx.fill();angle=next;});
 ctx.beginPath();ctx.arc(cx,cy,radius*.61,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.textAlign='center';ctx.fillStyle='#26384d';ctx.font='700 22px sans-serif';ctx.fillText(total,cx,cy+2);ctx.fillStyle='#8492a3';ctx.font='10px sans-serif';ctx.fillText('TOTAL TASKS',cx,cy+18);
 $('distribution-legend').innerHTML=entries.map(([vm,count],i)=>`<span class="legend-item"><i class="legend-dot" style="background:${chartColors[i%chartColors.length]}"></i>${escapeHtml(vm)} · ${count} (${(count/total*100).toFixed(1)}%)</span>`).join('');
}
function drawTaskChart(assignments){
 const c=prepareCanvas('task-chart');if(!c)return;const {ctx,w,h}=c;const rows=(assignments||[]).slice().sort((a,b)=>Number(a.task_id)-Number(b.task_id));
 if(!rows.length){ctx.fillStyle='#8a98a9';ctx.font='12px sans-serif';ctx.fillText('Belum ada data penugasan',12,24);return;}
 const left=48,right=16,top=14,bottom=38,pw=w-left-right,ph=h-top-bottom,values=rows.map(x=>Math.max(0,Number(x.predicted_seconds)||0)),max=Math.max(0.001,...values);
 ctx.strokeStyle='#e8edf3';ctx.fillStyle='#8492a3';ctx.font='10px sans-serif';ctx.textAlign='right';
 for(let i=0;i<=4;i++){const y=top+ph*i/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-right,y);ctx.stroke();ctx.fillText((max*(1-i/4)).toFixed(2),left-8,y+3);}
 const points=values.map((v,i)=>({x:left+(rows.length===1?pw/2:i/(rows.length-1)*pw),y:top+ph-(v/max)*(ph-5)}));
 ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.strokeStyle='#2878d0';ctx.lineWidth=2;ctx.stroke();
 points.forEach((p,i)=>{if(rows.length<=35||i%Math.ceil(rows.length/20)===0||i===points.length-1){ctx.beginPath();ctx.arc(p.x,p.y,3,0,Math.PI*2);ctx.fillStyle=chartColors[0];ctx.fill();}});
 ctx.fillStyle='#8492a3';ctx.textAlign='center';ctx.font='10px sans-serif';const step=Math.max(1,Math.ceil(rows.length/10));rows.forEach((r,i)=>{if(i%step===0||i===rows.length-1){const x=points[i].x;ctx.fillText(`#${r.task_id}`,x,h-14);}});
}
function renderCharts(data){drawLoadChart(data.loads);drawDistributionChart(data.assignments);drawTaskChart(data.assignments);}

function renderTasks(rows){
  $('task-rows').innerHTML=rows?.length?rows.map(t=>`<tr><td>#${t.task_id}</td><td>${num(t.lengthMI,0)}</td><td>${t.pes??'—'}</td><td><span class="vm-pill">${t.vm||'—'}</span></td><td>${t.host||'—'}</td><td>${seconds(t.predicted_seconds)}</td><td class="${t.fallback?'bad':'ok'}">${t.fallback?'YES':'NO'}</td></tr>`).join(''):'<tr><td colspan="7" class="muted">No mapping data yet</td></tr>';
}
function renderLogs(logs){
  latestLogs=logs||[]; const selected=showAllLogs?latestLogs:latestLogs.filter(x=>/error|failed|warning/i.test(x.line));
  $('log-list').innerHTML=selected.length?selected.slice().reverse().map(x=>{const line=x.line;const cls=/error|failed|exception/i.test(line)?'error':/completed|success|healthy|ready/i.test(line)?'success':'';return `<div class="log-line ${cls}"><span class="log-time">—</span><span class="log-source">${escapeHtml(x.file)}</span><span>${escapeHtml(line)}</span></div>`}).join(''):'<div class="muted">No log entries found in the latest session.</div>';
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
async function refresh(){
 try{
  const response=await fetch('/api/dashboard',{cache:'no-store'}); const d=await response.json();window.latestDashboardData=d;
  setText('updated','Updated '+new Date().toLocaleTimeString());
  if(!d.available){$('content').classList.add('hidden');$('empty').classList.remove('hidden');$('empty').textContent=d.message;return;}
  $('content').classList.remove('hidden');$('empty').classList.add('hidden');
  setText('session',d.session);setText('footer-session',d.session);setText('mode',d.mode);
  setText('tasks',num(d.task_count,0));setText('completed',num(d.completed,0));
  setText('completion-note',d.result_available?'Real worker execution':'No real execution result yet');
  setText('makespan',seconds(d.makespan));setText('elapsed',d.elapsed==null?'—':seconds(d.elapsed));
  const s=d.summary||{};
  setText('balance',s.load_balance_efficiency_percent==null?'—':num(s.load_balance_efficiency_percent)+'%');
  setText('imbalance',s.load_imbalance_percent==null?'—':num(s.load_imbalance_percent)+'%');
  setText('ideal',seconds(s.ideal_makespan_lower_bound_seconds));
  setText('gap',s.makespan_gap_from_ideal_percent==null?'—':num(s.makespan_gap_from_ideal_percent)+'%');
  const pct=d.task_count?Math.min(100,d.completed/d.task_count*100):0;
  $('progress-bar').style.width=pct+'%';setText('progress-label',num(pct,1)+'%');
  setText('progress-text',`${d.completed} of ${d.task_count} tasks completed`);
  renderBars(d.loads);renderCharts(d);renderTasks(d.assignments);renderLogs(d.logs);
  const workers=d.workers||[];setText('worker-note',workers.length?`${workers.filter(w=>w.healthy).length}/${workers.length} Docker workers running (container status)`:'Docker status unavailable or containers not found.');
  for(let i=1;i<=4;i++){const w=workers.find(x=>x.name===`llfd-vm-${i}`);$('vm'+i).classList.toggle('online',!!w?.healthy);$('vm'+i).title=w?.status||'Status unavailable';}
 }catch(e){setText('updated','API connection error');}
}
$('refresh').addEventListener('click',refresh);
$('clear-filter').addEventListener('click',()=>{showAllLogs=!showAllLogs;$('clear-filter').textContent=showAllLogs?'Show errors only':'Show all logs';renderLogs(latestLogs);});
window.addEventListener('resize',()=>{if(window.latestDashboardData)renderCharts(window.latestDashboardData);});
refresh();setInterval(refresh,3000);
