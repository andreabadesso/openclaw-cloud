from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from openclaw_api.config import settings
from openclaw_api.database import engine
from openclaw_api.deps import close_redis
from openclaw_api.routes import analytics, auth, billing, boxes, connections, health, internal, usage


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(title="OpenClaw Cloud API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(boxes.router)
app.include_router(usage.router)
app.include_router(analytics.router)
app.include_router(internal.router)
app.include_router(connections.router)
app.include_router(billing.router)
