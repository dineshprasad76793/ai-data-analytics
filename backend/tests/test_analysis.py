import pandas as pd
from app.analysis import profile, correlations, anomalies

def test_profile():
    df=pd.DataFrame({'a':[1,2,3,None],'category':['x','x','y','z'],'date':['2025-01-01','2025-01-02','2025-01-03','2025-01-04']})
    p=profile(df); assert p['rows']==4; assert 'a' in p['numeric_columns']; assert 'date' in p['date_columns']; assert p['missing_values']==1

def test_correlation():
    df=pd.DataFrame({'a':[1,2,3,4,5], 'b':[2,4,6,8,10]}); p=profile(df); c=correlations(df,p); assert c['pairs'][0]['pearson'] > .99
