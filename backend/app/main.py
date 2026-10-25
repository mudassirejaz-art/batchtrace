from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlsplit
from app.core.config import settings
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
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
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

# Same-origin reverse proxy (including local Vite proxy) needs no CORS.
# Reject wildcard, malformed and non-HTTPS production cross-origin settings.
_origins: list[str] = []
for _raw in settings.cors_origins.split(','):
    _origin = _raw.strip().rstrip('/')
    if not _origin:
        continue
    _parsed = urlsplit(_origin)
    if (
        _origin == '*'
        or _parsed.scheme not in {'http', 'https'}
        or not _parsed.hostname
        or _parsed.username is not None
        or _parsed.password is not None
        or _parsed.path
        or _parsed.query
        or _parsed.fragment
        or (settings.app_env == 'production' and _parsed.scheme != 'https')
    ):
        raise RuntimeError('Invalid CORS_ORIGINS. Use explicit HTTPS origins in production.')
    try:
        _parsed.port  # Validate numeric ports, when supplied.
    except ValueError as exc:
        raise RuntimeError('Invalid port in CORS_ORIGINS') from exc
    if _origin not in _origins:
        _origins.append(_origin)

if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=False,  # Bearer tokens, not cross-site cookies.
        allow_methods=['GET', 'POST', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'],
        allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'],
    )

@app.middleware('http')
async def batchtrace_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if request.url.path.startswith('/api/v1/'):
        response.headers['Cache-Control'] = 'no-store'
    if settings.app_env == 'production':
        # JSON API only: interactive docs are disabled in production.
        response.headers['Content-Security-Policy'] = "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response
