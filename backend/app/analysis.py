from __future__ import annotations
import io, json, math, re
from typing import Any
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

DATE_HINTS = ("date", "time", "timestamp", "month", "year")
ID_HINTS = ("id", "uuid", "code", "key")

def load_dataframe(raw: bytes, filename: str) -> pd.DataFrame:
    name = filename.lower()
    bio = io.BytesIO(raw)
    if name.endswith(".csv"):
        try: return pd.read_csv(bio)
        except UnicodeDecodeError:
            bio.seek(0); return pd.read_csv(bio, encoding="latin-1")
    if name.endswith(".tsv"):
        return pd.read_csv(bio, sep="\t")
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(bio)
    if name.endswith(".json"):
        obj = json.load(bio)
        if isinstance(obj, dict):
            if "data" in obj and isinstance(obj["data"], list): obj = obj["data"]
            else: obj = [obj]
        return pd.DataFrame(obj)
    raise ValueError("The file format is not supported.")

def _is_date_series(s: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(s): return True
    if s.dtype == "object":
        sample = s.dropna().astype(str).head(100)
        if sample.empty: return False
        name_score = any(h in str(s.name).lower() for h in DATE_HINTS)
        parsed = pd.to_datetime(sample, errors="coerce", utc=True)
        rate = parsed.notna().mean()
        return rate >= (0.75 if name_score else 0.95)
    return False

def profile(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty: raise ValueError("This dataset appears to be empty.")
    work = df.copy()
    date_cols=[]; numeric=[]; categorical=[]; boolean=[]; ids=[]
    for c in work.columns:
        s=work[c]
        cl=str(c).lower()
        if pd.api.types.is_bool_dtype(s): boolean.append(c)
        elif pd.api.types.is_numeric_dtype(s): numeric.append(c)
        elif _is_date_series(s): date_cols.append(c)
        else: categorical.append(c)
        nun=s.nunique(dropna=True)
        if nun == len(s) and any(h in cl for h in ID_HINTS): ids.append(c)
    cols=[]
    for c in work.columns:
        s=work[c]; miss=int(s.isna().sum()); non=s.dropna()
        item={"name":c,"dtype":str(s.dtype),"unique":int(s.nunique(dropna=True)),"missing":miss,"missing_pct":round(miss/len(s)*100,2)}
        if c in numeric:
            x=pd.to_numeric(s, errors="coerce").dropna()
            item.update({"min":safe_num(x.min()),"max":safe_num(x.max()),"mean":safe_num(x.mean()),"median":safe_num(x.median()),"std":safe_num(x.std()),"mode":safe_num(x.mode().iloc[0]) if not x.mode().empty else None,"q1":safe_num(x.quantile(.25)),"q3":safe_num(x.quantile(.75)),"skewness":safe_num(x.skew()),"kurtosis":safe_num(x.kurt())})
        elif c in categorical or c in boolean:
            vc=s.value_counts(dropna=True).head(10); total=max(1,vc.sum())
            item["top_categories"]= [{"value":str(k),"count":int(v),"pct":round(float(v/total*100),2)} for k,v in vc.items()]
        elif c in date_cols:
            d=pd.to_datetime(s, errors="coerce", utc=True).dropna(); item.update({"earliest":d.min().isoformat() if len(d) else None,"latest":d.max().isoformat() if len(d) else None})
        cols.append(item)
    missing_total=int(work.isna().sum().sum()); cells=max(1,work.shape[0]*work.shape[1]); dup=int(work.duplicated().sum())
    quality=max(0,min(100,100 - 55*missing_total/cells - 35*dup/max(1,len(work))))
    return {"rows":len(work),"columns":work.shape[1],"numeric_columns":numeric,"categorical_columns":categorical,"date_columns":date_cols,"boolean_columns":boolean,"possible_id_columns":ids,"missing_values":missing_total,"duplicate_rows":dup,"file_size":None,"data_quality_score":round(quality,1),"columns":cols}

def safe_num(x):
    try:
        if pd.isna(x): return None
        return float(x)
    except Exception:return None

def insights(df: pd.DataFrame, p: dict[str,Any]) -> dict[str,Any]:
    out={"kpis":[],"trends":[],"anomalies":[],"correlations":[],"comparisons":[],"recommendations":[]}
    nums=p["numeric_columns"]
    for c in nums[:8]:
        s=pd.to_numeric(df[c],errors="coerce").dropna()
        if not len(s): continue
        out["kpis"].append({"label":f"Average {c}","value":round(float(s.mean()),2)})
        q1,q3=s.quantile(.25),s.quantile(.75); iqr=q3-q1
        mask=(s<q1-1.5*iqr)|(s>q3+1.5*iqr)
        if mask.any(): out["anomalies"].append({"column":c,"count":int(mask.sum()),"pct":round(float(mask.mean()*100),2),"method":"IQR"})
    if len(nums)>=2:
        corr=df[nums].corr(numeric_only=True)
        for i,a in enumerate(nums):
            for b in nums[i+1:]:
                v=corr.loc[a,b]
                if pd.notna(v) and abs(v)>=.7: out["correlations"].append({"a":a,"b":b,"pearson":round(float(v),3),"strength":"strong"})
    for dcol in p["date_columns"][:1]:
        d=pd.to_datetime(df[dcol],errors="coerce"); valid=d.notna()
        if valid.sum()>=6 and nums:
            v=nums[0]; ts=pd.DataFrame({"d":d[valid],"v":pd.to_numeric(df.loc[valid,v],errors="coerce")}).dropna().sort_values("d")
            if len(ts)>=6:
                grp=ts.set_index("d")["v"].resample("ME").mean().dropna()
                if len(grp)>=2:
                    delta=float(grp.iloc[-1]-grp.iloc[0]); direction="increased" if delta>0 else "decreased"
                    out["trends"].append({"column":v,"granularity":"monthly","direction":direction,"change":round(delta,2)})
    if p["missing_values"]: out["recommendations"].append("Review columns with missing values before relying on model results.")
    if p["duplicate_rows"]: out["recommendations"].append("Review duplicate rows; remove them only when they represent accidental duplicates.")
    if out["correlations"]: out["recommendations"].append("Investigate strong correlations while remembering that correlation does not imply causation.")
    return out

def correlations(df,p):
    nums=p["numeric_columns"]
    if len(nums)<2:return {"matrix":{},"pairs":[]}
    pear=df[nums].corr(method="pearson"); spear=df[nums].corr(method="spearman")
    pairs=[]
    for i,a in enumerate(nums):
        for b in nums[i+1:]:
            pairs.append({"a":a,"b":b,"pearson":safe_num(pear.loc[a,b]),"spearman":safe_num(spear.loc[a,b])})
    return {"matrix":pear.round(3).fillna(0).to_dict(),"pairs":sorted(pairs,key=lambda x:abs(x["pearson"] or 0),reverse=True)[:20]}

def anomalies(df,p):
    nums=p["numeric_columns"]
    if not nums:return {"count":0,"rows":[]}
    x=df[nums].apply(pd.to_numeric,errors="coerce").dropna()
    if len(x)<20:return {"count":0,"rows":[],"message":"There isn't enough data to perform robust anomaly detection."}
    model=IsolationForest(random_state=42,contamination="auto",n_estimators=150)
    pred=model.fit_predict(StandardScaler().fit_transform(x))
    score=-model.score_samples(StandardScaler().fit_transform(x))
    ix=x.index[pred==-1]
    rows=df.loc[ix].head(25).replace({np.nan:None}).to_dict(orient="records")
    return {"count":int(len(ix)),"pct":round(float(len(ix)/len(x)*100),2),"rows":rows,"method":"Isolation Forest"}

def regression(df,p,target):
    if not target or target not in df.columns:return {"available":False}
    nums=[c for c in p["numeric_columns"] if c!=target]
    y=pd.to_numeric(df[target],errors="coerce")
    if len(nums)<1:return {"available":False}
    clean=df[nums].apply(pd.to_numeric,errors="coerce").copy(); clean["__y"]=y; clean=clean.dropna()
    if len(clean)<20:return {"available":False,"reason":"Not enough complete rows."}
    X=clean[nums]; model=LinearRegression().fit(X,clean["__y"])
    return {"available":True,"type":"linear_regression","target":target,"r2":round(float(model.score(X,clean["__y"])),4),"coefficients":{c:round(float(v),4) for c,v in zip(nums,model.coef_)}}

def safe_operation(df,p,question:str)->dict[str,Any]:
    q=question.lower()
    if "average" in q or "mean" in q:
        c=next((c for c in p["numeric_columns"] if c.lower() in q), p["numeric_columns"][0] if p["numeric_columns"] else None)
        if c:return {"type":"metric","column":c,"metric":"mean","value":safe_num(pd.to_numeric(df[c],errors="coerce").mean())}
    if "highest" in q or "maximum" in q or "max" in q:
        c=next((c for c in p["numeric_columns"] if c.lower() in q), p["numeric_columns"][0] if p["numeric_columns"] else None)
        if c:
            i=pd.to_numeric(df[c],errors="coerce").idxmax(); return {"type":"row","column":c,"value":safe_num(df.loc[i,c]),"row":df.loc[i].replace({np.nan:None}).to_dict()}
    if "top" in q and "10" in q:
        c=next((c for c in p["numeric_columns"] if c.lower() in q), p["numeric_columns"][0] if p["numeric_columns"] else None)
        if c:return {"type":"table","column":c,"rows":df.sort_values(c,ascending=False).head(10).replace({np.nan:None}).to_dict(orient="records")}
    if "correlation" in q:
        return {"type":"correlation","result":correlations(df,p)}
    return {"type":"insufficient","message":"The available data is insufficient to determine this."}
