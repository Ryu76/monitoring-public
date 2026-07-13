from fastapi import APIRouter
from . import auth, users, codes

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["Admin Auth"])
router.include_router(users.router, prefix="/users", tags=["Admin Users"])
router.include_router(codes.router, prefix="/codes", tags=["Admin Codes"])
