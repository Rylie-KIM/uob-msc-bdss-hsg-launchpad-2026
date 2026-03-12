from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.routers import auth, chat, sleep, healthkit, alerts

load_dotenv()

app = FastAPI(title="ClearHealth API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your Lovable domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(sleep.router, prefix="/api")
app.include_router(healthkit.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")


@app.on_event("startup")
async def startup():
    print("\n  🚀 ClearHealth API running")
    print("  📖 Docs:   http://localhost:8000/docs")
    print("  ❤️  Health: http://localhost:8000/health\n")


@app.get("/health")
def health_check():
    return {"status": "ok"}
