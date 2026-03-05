from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from . import models as _models  # noqa: F401
from .middleware.rate_limit import rate_limit_middleware
from .routers.health import router as health_router
from .routers.jobs import router as jobs_router
from .routers.maintenance import router as maintenance_router
from .routers.reports import router as reports_router
from .routers.uploads import router as uploads_router
from .routers.usage import router as usage_router

app = FastAPI(title=settings.app_name)
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(rate_limit_middleware)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(health_router)
app.include_router(jobs_router)
app.include_router(maintenance_router)
app.include_router(reports_router)
app.include_router(uploads_router)
app.include_router(usage_router)
