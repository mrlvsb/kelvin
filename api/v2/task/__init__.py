from ninja import Router

from .submit.comment import router as submit_comment_router
from .submit.default import router as submit_default_router

router = Router(tags=["Task"])
router.add_router("/{assignment_id}/{login}/{submit_num}", submit_default_router)
router.add_router("/{assignment_id}/{login}/{submit_num}/comment", submit_comment_router)
