from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.core.config import settings
from app.core.security import init_firebase
from app.core.rate_limit import limiter

from app.api.v1 import auth, users, friends, tickets, games, arcades, reservations, scores, promos, admin

# Initialisation Firebase
init_firebase()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG
)

# 🔥 Rate limiter setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🔥 Middleware slowapi
app.add_middleware(SlowAPIMiddleware)

# Routes
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(friends.router, prefix="/api/v1/friends", tags=["friends"])
app.include_router(tickets.router, prefix="/api/v1/tickets", tags=["tickets"])
app.include_router(games.router, prefix="/api/v1/games", tags=["games"])
app.include_router(arcades.router, prefix="/api/v1/arcades", tags=["arcades"])
app.include_router(reservations.router, prefix="/api/v1/reservations", tags=["reservations"])
app.include_router(scores.router, prefix="/api/v1/scores", tags=["scores"])
app.include_router(promos.router, prefix="/api/v1/promos", tags=["promos"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/")
async def root():
    return {"message": "Arcade API", "version": settings.VERSION}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}