"""Admin sub-routers aggregator."""
from fastapi import APIRouter
from .dashboard import router as dashboard_router
from .applications import router as applications_router
from .orders import router as orders_router
from .withdrawals import router as withdrawals_router
from .refunds import router as refunds_router
from .config import router as config_router
from .users import router as users_router
from .audit import router as audit_router
from .commission import router as commission_router

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
router.include_router(dashboard_router)
router.include_router(applications_router)
router.include_router(orders_router)
router.include_router(withdrawals_router)
router.include_router(refunds_router)
router.include_router(config_router)
router.include_router(users_router)
router.include_router(audit_router)
router.include_router(commission_router)