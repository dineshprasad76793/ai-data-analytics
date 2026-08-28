from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json, time
from .config import APP_NAME, MAX_FILE_SIZE, ALLOWED_ORIGINS, MAX_ROWS_FOR_BROWSER
from .storage import *
from .analysis import *
from .ai import explain
from .report import build_pdf
from .models import QueryRequest, CleanRequest

app=FastAPI(title=APP_NAME)
RATE={}

def allow(request, limit=30, window=60):
    key=request.client.host if request.client else "unknown"; now=time.time(); bucket=[t for t in RATE.get(key,[]) if now-t<window]
    if len(bucket)>=limit: return False
    bucket.append(now); RATE[key]=bucket; return True
app.add_middleware(CORSMiddleware,allow_origins=ALLOWED_ORIGINS,allow_credentials=True,allow_methods=["GET","POST","DELETE"],allow_headers=["*"])

@app.middleware("http")
async def cleanup(request: Request, call_next):
    cleanup_old(); return await call_next(request)

def save_df(dataset_id, df):
    path_for(dataset_id).write_bytes(df.to_pickle(None) if False else b"")

@app.get("/api/health")
def health(): return {"status":"ok","app":APP_NAME}

@app.post("/api/upload")
async def upload(request: Request, file: UploadFile=File(...)):
    if not allow(request, limit=10): raise HTTPException(429,"Too many uploads. Please try again later.")
    raw=await file.read()
    if len(raw)>MAX_FILE_SIZE: raise HTTPException(413,"The file is too large.")
    if not file.filename: raise HTTPException(400,"Please choose a file.")
    try: df=load_dataframe(raw,file.filename)
    except ValueError as e: raise HTTPException(400,str(e))
    except Exception: raise HTTPException(400,"We could not read this file safely.")
    if df.empty: raise HTTPException(400,"This dataset appears to be empty.")
    did=new_id(); df.to_pickle(path_for(did)); meta={"filename":file.filename,"size":len(raw)}; meta_path(did).write_text(json.dumps(meta));
    p=profile(df); p["file_size"]=len(raw)
    return {"dataset_id":did,"profile":p,"preview":df.head(MAX_ROWS_FOR_BROWSER).replace({float('nan'):None}).to_dict(orient="records")}

@app.get("/api/{dataset_id}/analysis")
def analysis(dataset_id:str):
    pth=path_for(dataset_id)
    if not pth.exists(): raise HTTPException(404,"Dataset not found or expired.")
    df=__import__('pandas').read_pickle(pth); p=profile(df); p["file_size"]=meta_path(dataset_id).stat().st_size if meta_path(dataset_id).exists() else None
    return {"profile":p,"insights":insights(df,p),"correlations":correlations(df,p),"anomalies":anomalies(df,p)}

@app.get("/api/{dataset_id}/charts")
def charts(dataset_id:str):
    import pandas as pd
    pth=path_for(dataset_id)
    if not pth.exists(): raise HTTPException(404,"Dataset not found or expired.")
    df=pd.read_pickle(pth); p=profile(df); out=[]
    nums=p["numeric_columns"]; cats=p["categorical_columns"]; dates=p["date_columns"]
    if dates and nums:
        dcol=dates[0]; vcol=nums[0]
        x=pd.DataFrame({"date":pd.to_datetime(df[dcol],errors="coerce"),"value":pd.to_numeric(df[vcol],errors="coerce")}).dropna()
        if len(x):
            g=x.set_index("date")["value"].resample("ME").sum().dropna().tail(24)
            out.append({"type":"line","title":f"{vcol} over time","xKey":"label","yKey":"value","data":[{"label":d.strftime("%Y-%m"),"value":round(float(v),2)} for d,v in g.items()]})
    if cats and nums:
        c=cats[0]; v=nums[0]; g=df.groupby(c,dropna=False)[v].sum().sort_values(ascending=False).head(10)
        out.append({"type":"bar","title":f"{v} by {c}","xKey":"label","yKey":"value","data":[{"label":str(k),"value":round(float(val),2)} for k,val in g.items()]})
    return {"charts":out}

@app.get("/api/{dataset_id}/forecast")
def forecast(dataset_id:str):
    import pandas as pd, numpy as np
    from sklearn.linear_model import LinearRegression
    pth=path_for(dataset_id)
    if not pth.exists(): raise HTTPException(404,"Dataset not found or expired.")
    df=pd.read_pickle(pth); p=profile(df); dates=p["date_columns"]; nums=p["numeric_columns"]
    if not dates or not nums: return {"available":False,"message":"We could not detect a suitable date column for forecasting."}
    dcol,vcol=dates[0],nums[0]
    x=pd.DataFrame({"date":pd.to_datetime(df[dcol],errors="coerce"),"value":pd.to_numeric(df[vcol],errors="coerce")}).dropna()
    g=x.set_index("date")["value"].resample("ME").sum().dropna()
    if len(g)<6: return {"available":False,"message":"There isn't enough historical data to perform this analysis."}
    y=g.to_numpy(); t=np.arange(len(y)).reshape(-1,1); model=LinearRegression().fit(t,y); h=min(6,max(3,len(y)//3)); ft=np.arange(len(y),len(y)+h).reshape(-1,1); pred=model.predict(ft)
    residuals=y-model.predict(t); sigma=float(np.std(residuals,ddof=1)) if len(residuals)>1 else 0.0; future=pd.date_range(g.index[-1]+pd.offsets.MonthEnd(1),periods=h,freq="ME")
    return {"available":True,"method":"Linear trend forecast","date_column":dcol,"value_column":vcol,"historical":[{"date":d.strftime("%Y-%m"),"value":round(float(v),2)} for d,v in g.items()],"forecast":[{"date":d.strftime("%Y-%m"),"value":round(float(v),2),"low":round(float(v-1.96*sigma),2),"high":round(float(v+1.96*sigma),2)} for d,v in zip(future,pred)]}

@app.post("/api/query")
async def query(request: Request, req:QueryRequest):
    if not allow(request, limit=30): raise HTTPException(429,"Too many analysis requests. Please try again later.")
    pth=path_for(req.dataset_id)
    if not pth.exists(): raise HTTPException(404,"Dataset not found or expired.")
    import pandas as pd
    df=pd.read_pickle(pth); p=profile(df); result=safe_operation(df,p,req.question); ai=await explain(req.question,result)
    return {"result":result,"explanation":ai["text"]}

@app.post("/api/clean")
def clean(req:CleanRequest):
    import pandas as pd
    pth=path_for(req.dataset_id)
    if not pth.exists(): raise HTTPException(404,"Dataset not found or expired.")
    df=pd.read_pickle(pth); original=df.copy()
    for a in req.actions:
        typ=a.get("type"); col=a.get("column")
        if typ=="trim_whitespace" and col in df.columns: df[col]=df[col].astype("string").str.strip()
        elif typ=="drop_duplicates": df=df.drop_duplicates()
        elif typ=="fill_missing" and col in df.columns:
            method=a.get("method","median");
            if method=="median" and pd.api.types.is_numeric_dtype(df[col]): df[col]=df[col].fillna(df[col].median())
            elif method=="mean" and pd.api.types.is_numeric_dtype(df[col]): df[col]=df[col].fillna(df[col].mean())
            elif method=="mode":
                m=df[col].mode();
                if not m.empty: df[col]=df[col].fillna(m.iloc[0])
            elif method=="ffill": df[col]=df[col].ffill()
            elif method=="bfill": df[col]=df[col].bfill()
        elif typ=="rename" and col in df.columns and a.get("new_name"): df=df.rename(columns={col:a["new_name"]})
        elif typ=="drop_rows_with_missing" and col in df.columns: df=df.dropna(subset=[col])
    df.to_pickle(pth); p=profile(df); return {"profile":p,"removed_rows":int(len(original)-len(df))}

@app.get("/api/{dataset_id}/export/cleaned.csv")
def export_csv(dataset_id:str):
    import pandas as pd
    p=path_for(dataset_id)
    if not p.exists(): raise HTTPException(404,"Dataset not found or expired.")
    out=p.with_suffix('.csv'); pd.read_pickle(p).to_csv(out,index=False); return FileResponse(out,filename="cleaned_dataset.csv",media_type="text/csv")

@app.get("/api/{dataset_id}/report.pdf")
def report(dataset_id:str):
    import pandas as pd
    pth=path_for(dataset_id)
    if not pth.exists(): raise HTTPException(404,"Dataset not found or expired.")
    df=pd.read_pickle(pth); p=profile(df); ins=insights(df,p); out=build_pdf(dataset_id,p,ins); return FileResponse(out,filename="analytics_report.pdf",media_type="application/pdf")

@app.get("/api/{dataset_id}/export/cleaned.xlsx")
def export_xlsx(dataset_id:str):
    import pandas as pd
    p=path_for(dataset_id)
    if not p.exists(): raise HTTPException(404,"Dataset not found or expired.")
    out=p.with_suffix('.xlsx'); pd.read_pickle(p).to_excel(out,index=False); return FileResponse(out,filename="cleaned_dataset.xlsx",media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.delete("/api/{dataset_id}")
def delete_dataset(dataset_id:str):
    path_for(dataset_id).unlink(missing_ok=True); meta_path(dataset_id).unlink(missing_ok=True); return {"deleted":True}

@app.post("/api/demo")
def demo():
    import pandas as pd, numpy as np
    rng=np.random.default_rng(7); n=240; dates=pd.date_range("2025-01-01",periods=n,freq="D")
    products=rng.choice(["Alpha","Beta","Gamma","Delta"],n,p=[.35,.3,.2,.15]); regions=rng.choice(["North","South","East","West"],n)
    units=rng.integers(5,80,n); price=np.select([products=="Alpha",products=="Beta",products=="Gamma"],[120,90,70],default=55)+rng.normal(0,5,n)
    revenue=units*price; revenue[20]=revenue[20]*4; revenue[180]=revenue[180]*.3
    df=pd.DataFrame({"date":dates,"product":products,"region":regions,"units":units,"unit_price":price.round(2),"revenue":revenue.round(2)})
    did=new_id(); df.to_pickle(path_for(did)); meta_path(did).write_text(json.dumps({"filename":"demo.csv","size":len(df.to_csv(index=False))})); p=profile(df); p["file_size"]=len(df.to_csv(index=False)); return {"dataset_id":did,"profile":p,"preview":df.head(100).to_dict(orient="records")}

frontend_dist=Path(__file__).resolve().parents[2]/"frontend"/"dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist,html=True), name="frontend")
