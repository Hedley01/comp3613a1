from fastapi import Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AdvisorDep
from app.dependencies.session import SessionDep
from app.repositories.advisor_reviews import AdvisorReviewRepository
from app.services.advisor_review_service import AdvisorReviewService
from app.utilities.flash import flash

from . import router, templates


@router.get(
    "/advisor/reviews",
    response_class=HTMLResponse,
    name="advisor_reviews_view",
)
async def advisor_reviews_view(
    request: Request,
    user: AdvisorDep,
    db: SessionDep,
    plan_id: int | None = None,
):
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated account is missing its database identifier.",
        )
    inbox = AdvisorReviewService(
        AdvisorReviewRepository(db)
    ).get_inbox(user.id, plan_id)

    return templates.TemplateResponse(
        request=request,
        name="advisor_reviews.html",
        context={"user": user, "inbox": inbox},
    )


@router.post(
    "/advisor/reviews/{plan_id}",
    name="advisor_review_action",
)
async def advisor_review_action(
    request: Request,
    user: AdvisorDep,
    db: SessionDep,
    plan_id: int,
    decision: str = Form(),
    feedback: str = Form(default=""),
):
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated account is missing its database identifier.",
        )
    result = AdvisorReviewService(
        AdvisorReviewRepository(db)
    ).review_plan(
        user_id=user.id,
        plan_id=plan_id,
        decision=decision,
        feedback=feedback,
    )
    flash(
        request,
        result.message,
        "success" if result.succeeded else "danger",
    )
    return RedirectResponse(
        url=request.url_for("advisor_reviews_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/advisor/reviews/{plan_id}/withdraw",
    name="advisor_withdraw_plan",
)
async def advisor_withdraw_plan(
    request: Request,
    user: AdvisorDep,
    db: SessionDep,
    plan_id: int,
):
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated account is missing its database identifier.",
        )
    result = AdvisorReviewService(AdvisorReviewRepository(db)).withdraw_plan(
        user_id=user.id, plan_id=plan_id
    )
    flash(
        request,
        result.message,
        "success" if result.succeeded else "danger",
    )
    return RedirectResponse(
        url=request.url_for("advisor_reviews_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )