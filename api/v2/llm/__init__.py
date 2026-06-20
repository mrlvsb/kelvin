from ninja import Router

from .default import router as default_router
from .prompts import router as prompts_router
from .suggestions import router as suggestions_router

router = Router(tags=["AI Review"])
router.add_router("", default_router)
router.add_router("prompts/", prompts_router)
router.add_router("suggestions/", suggestions_router)
