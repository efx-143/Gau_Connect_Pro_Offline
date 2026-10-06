const $=s=>document.querySelector(s);
async function api(url,opts={}){const r=await fetch(url,opts);const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error||"Request failed");return d}
async function refreshStats(){const x=await api("/api/stats");$("#sFarmers").textContent=x.farmers;$("#sCows").textContent=x.cows;$("#sSurveys").textContent=x.surveys}
function photoCell(p){return p?`<img src="${p}" alt="photo">`:"—"}
let farmerCache=[];
async function loadTables(){farmerCache=await api("/api/farmers");const surveys=await api("/api/surveys");renderFarmers(farmerCache);$("#surveyRows").innerHTML=surveys.map(x=>`<tr><td>${photoCell(x.photo)}</td><td>${esc(x.name)}</td><td>${esc(x.area)}</td><td>${x.cows}</td><td>${esc(x.water)}</td><td>${esc(x.clean)}</td><td><button class="delete" onclick="del('surveys',${x.id})">Delete</button></td></tr>`).join("")||'<tr><td colspan="7">No surveys yet.</td></tr>'}
function renderFarmers(rows){$("#farmersRows").innerHTML=rows.map(x=>`<tr><td>${photoCell(x.photo)}</td><td>${esc(x.name)}</td><td>${esc(x.phone)}</td><td>${esc(x.area)}</td><td>${x.cows}</td><td><button class="delete" onclick="del('farmers',${x.id})">Delete</button></td></tr>`).join("")||'<tr><td colspan="6">No farmers yet.</td></tr>'}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]))}
async function del(t,id){if(!confirm("Delete this record?"))return;await api(`/api/${t}?id=${id}`,{method:"DELETE"});await loadTables();await refreshStats()}
$("#farmerForm").addEventListener("submit",async e=>{e.preventDefault();const m=$("#farmerMsg");try{await api("/api/farmers",{method:"POST",body:new FormData(e.target)});e.target.reset();m.textContent="Saved successfully.";await refreshStats()}catch(x){m.textContent=x.message}})
$("#surveyForm").addEventListener("submit",async e=>{e.preventDefault();const m=$("#surveyMsg");try{await api("/api/surveys",{method:"POST",body:new FormData(e.target)});e.target.reset();m.textContent="Survey saved.";await refreshStats()}catch(x){m.textContent=x.message}})
$("#loginBtn").onclick=async()=>{try{await api("/api/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:$("admin").value,password:$("gauconnect").value})});$("#login").hidden=true;$("#dash").hidden=false;await loadTables()}catch(e){$("#loginMsg").textContent="Invalid login."}}
$("#logout").onclick=()=>{$("#dash").hidden=true;$("#login").hidden=false;$("#p").value=""}
$("#search").oninput=()=>{const q=$("#search").value.toLowerCase();renderFarmers(farmerCache.filter(x=>(x.name+" "+x.phone+" "+x.area).toLowerCase().includes(q)))}
refreshStats()
