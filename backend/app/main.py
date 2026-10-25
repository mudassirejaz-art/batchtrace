from fastapi import FastAPI
from app.features.auth.router import router as auth_router
from app.features.organizations.router import router as organizations_router
from app.features.suppliers.router import router as suppliers_router
from app.features.products.router import router as products_router
from app.features.lots.router import router as lots_router
from app.features.return_policies.router import policy_router, evaluation_router
from app.features.imports.router import router as imports_router
from app.features.recovery.router import router as recovery_router

app = FastAPI(
    title="BatchTrace Recovery API",
    version="0.1.0",
)

@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "batchtrace"}

app.include_router(auth_router)
app.include_router(organizations_router)

app.include_router(suppliers_router)
app.include_router(products_router)
app.include_router(lots_router)
app.include_router(policy_router)
app.include_router(evaluation_router)
app.include_router(imports_router)
app.include_router(recovery_router)
from app.features.verifications.router import router as verifications_router
app.include_router(verifications_router)
from app.features.claims.router import router as claims_router
app.include_router(claims_router)
from app.features.settlements.router import router as settlements_router
app.include_router(settlements_router)

from app.features.team.router import router as team_router
app.include_router(team_router)
