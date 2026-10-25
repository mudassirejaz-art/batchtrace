"""Local-only role authorization regression. Creates separate disposable-named test users; never deletes existing records."""
import asyncio
from uuid import uuid4

import httpx
from sqlalchemy import text
from app.db.session import engine
from app.main import app
from smoke_team import register, expect


async def main():
    if engine.url.host not in {'127.0.0.1','localhost','::1'} or engine.url.database!='batchtrace_db' or engine.url.username!='batchtrace_dev':
        raise SystemExit('STOP: Wrong DB for role smoke')
    async with engine.connect() as conn:
        assert await conn.scalar(text('SELECT current_database()'))=='batchtrace_db'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
        suffix=uuid4().hex[:12]
        _,owner,auth_owner=await register(client,suffix+'o')
        admin_email,admin,auth_admin=await register(client,suffix+'a')
        staff_email,staff,auth_staff=await register(client,suffix+'s')
        viewer_email,viewer,auth_viewer=await register(client,suffix+'v')
        base='/api/v1/organizations/'+owner['organization_id']
        await expect(client,'POST',base+'/team',201,headers=auth_owner,json={'email':admin_email,'role':'admin'})
        await expect(client,'POST',base+'/team',201,headers=auth_owner,json={'email':staff_email,'role':'staff'})
        await expect(client,'POST',base+'/team',201,headers=auth_owner,json={'email':viewer_email,'role':'viewer'})
        orgs=(await expect(client,'GET','/api/v1/organizations/me',200,headers=auth_admin)).json()
        assert any(o['id']==owner['organization_id'] and o['role']=='admin' for o in orgs)
        assert any(o['id']==admin['organization_id'] and o['role']=='owner' for o in orgs)
        print('PASS: Newly joined workspace appears; private workspace owner is independent')
        await expect(client,'GET',base+'/team',403,headers=auth_viewer)
        await expect(client,'GET',base+'/team',403,headers=auth_staff)
        await expect(client,'GET',base+'/team',200,headers=auth_admin)
        await expect(client,'POST',base+'/return-policies',403,headers=auth_staff,json={})
        await expect(client,'POST',base+'/return-policies',403,headers=auth_viewer,json={})
        print('PASS: Team directory and policy writes protected from unauthorized roles')
        fake=uuid4()
        await expect(client,'GET',base+f'/recovery/claims/{fake}/credit-summary',403,headers=auth_viewer)
        await expect(client,'GET',base+f'/recovery/claims/{fake}/credit-receipts',403,headers=auth_viewer)
        await expect(client,'GET',base+'/suppliers',200,headers=auth_viewer)
        await expect(client,'POST',base+'/suppliers',403,headers=auth_viewer,json={'code':'VIEW-001','name':'Not allowed'})
        print('PASS: Financial privacy and read-only viewer enforcement')
    await engine.dispose()
    print('PASS: Step 23 role access smoke completed')

if __name__=='__main__':asyncio.run(main())
