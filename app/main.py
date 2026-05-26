from fastapi import FastAPI

from app.api.routes.receptionist import router as receptionist_router
from app.config import settings

app = FastAPI(title=settings.app_name)
app.include_router(receptionist_router, prefix=settings.api_prefix)
