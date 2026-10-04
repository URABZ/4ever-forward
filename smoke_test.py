"""Run after dependencies install: python smoke_test.py"""
import os, re, tempfile
from pathlib import Path
from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as d:
    os.environ['DATABASE_URL'] = f"sqlite:///{Path(d)/'test.sqlite3'}"
    os.environ['FF_ENV'] = 'development'
    os.environ['FF_COOKIE_SECURE'] = '0'
    os.environ['FF_PUBLIC_BASE_URL'] = 'http://testserver'
    import app
    mails=[]
    app.send_email=lambda to, subject, body: mails.append((to,subject,body))
    c=TestClient(app.app)
    assert c.get('/api/health').status_code == 200
    r=c.post('/api/auth/register',json={'email':'smoke@example.com','password':'smoketestpassword123'})
    assert r.status_code == 200
    csrf=r.json()['csrf']
    assert c.put('/api/state',json={'base_version':0,'state':{'4everForwardTasksV2':'[]'}},headers={'X-CSRF-Token':csrf}).status_code == 403
    token=re.search(r'token=([^\s]+)',mails[-1][2]).group(1)
    assert c.get('/api/auth/verify',params={'token':token},follow_redirects=False).status_code == 303
    csrf=c.get('/api/auth/me').json()['csrf']
    r=c.put('/api/state',json={'base_version':0,'state':{'4everForwardTasksV2':'[]'}},headers={'X-CSRF-Token':csrf})
    assert r.status_code == 200
    assert c.get('/api/account/export').status_code == 200
    print('smoke test passed')
