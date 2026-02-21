from fastapi import APIRouter

from .agent import router as agent_router
from .customer import router as customer_router

router = APIRouter()
router.include_router(customer_router)
router.include_router(agent_router)
