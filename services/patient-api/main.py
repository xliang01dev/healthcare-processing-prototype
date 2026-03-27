from contextlib import asynccontextmanager

from fastapi import FastAPI

import patients_router as patients


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No NATS, no asyncpg — reads via downstream service calls only.
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(patients.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-api"}
