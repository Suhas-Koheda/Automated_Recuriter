from fastapi import APIRouter
from app.api.routes import router as api_router

router = APIRouter()

# Include all routes from the routes module
router.include_router(api_router, prefix="")