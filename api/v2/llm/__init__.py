from ninja import Router

from .default import router as default_router
from .prompt import router as prompt_router
from .suggestions import router as suggestions_router

router = Router(tags=["AI Review"])
router.add_router("", default_router)
router.add_router("prompt/", prompt_router)
router.add_router("suggestions/", suggestions_router)
