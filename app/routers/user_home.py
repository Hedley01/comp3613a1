from fastapi import HTTPException, Request, status
from fastapi.responses import HTMLResponse

from app.dependencies.auth import AuthDep
from app.dependencies.session import SessionDep
from app.repositories.progress import ProgressRepository
from app.services.progress_service import ProgressService

from . import router, templates


@router.get("/app", response_class=HTMLResponse, name="user_home_view")
@router.get("/progress", response_class=HTMLResponse, name="progress_view")
async def user_home_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated account is missing its database identifier.",
        )
    progress = ProgressService(ProgressRepository(db)).calculate_progress_for_user_id(
        user.id
    )
    return templates.TemplateResponse(
        request=request,
        name="progress.html",
        context={
            "user": user,
            "progress": progress,
        },
    )