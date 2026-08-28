const API=import.meta.env.VITE_API_URL||'/api';
async function req(path:string,opts:RequestInit={}){const r=await fetch(API+path,opts); if(!r.ok){let m='Request failed';try{const j=await r.json();m=j.detail||m}catch{} throw new Error(m)} return r;}
export async function upload(file:File){const f=new FormData();f.append('file',file);return (await req('/upload',{method:'POST',body:f})).json()}
export async function demo(){return (await req('/demo',{method:'POST'})).json()}
export async function analysis(id:string){return (await req(`/${id}/analysis`)).json()}
export async function query(id:string,q:string){return (await req('/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset_id:id,question:q})})).json()}
export function reportUrl(id:string){return API+`/${id}/report.pdf`}; export function csvUrl(id:string){return API+`/${id}/export/cleaned.csv`}
export async function clean(id:string,actions:any[]){return (await req('/clean',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dataset_id:id,actions})})).json()}

export async function charts(id:string){return (await req(`/${id}/charts`)).json()}
export async function forecast(id:string){return (await req(`/${id}/forecast`)).json()}
