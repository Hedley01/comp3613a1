from typing import Annotated

from fastapi import Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AuthDep
from app.dependencies.session import SessionDep
from app.repositories.course_plan import CoursePlanRepository
from app.services.course_plan_service import (
    TARGET_SEMESTERS,
    CoursePlanService,
)
from app.utilities.flash import flash

from . import router, templates


@router.get("/course-plan", response_class=HTMLResponse, name="course_plan_view")
async def course_plan_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    target_semester: str | None = None,
    edit_plan_id: int | None = None,
):
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated account is missing its database identifier.",
        )
    service = CoursePlanService(CoursePlanRepository(db))
    if edit_plan_id is None:
        plan_result = service.get_plan_page(
            user_id=user.id,
            target_semester=target_semester or TARGET_SEMESTERS[0],
        )
    else:
        plan_result = service.get_editable_plan_page(
            user_id=user.id,
            plan_id=edit_plan_id,
        )
    return templates.TemplateResponse(
        request=request,
        name="course-plan.html",
        context={
            "user": user,
            "plan": plan_result.plan_page,
            "page_errors": plan_result.errors,
            "editing_plan_id": edit_plan_id,
        },
    )


@router.post("/course-plan", response_class=HTMLResponse, name="course_plan_action")
async def course_plan_action(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    target_semester: str = Form(),
    selected_course_codes: Annotated[list[str] | None, Form()] = None,
    action: str = Form(default="submit"),
    edit_plan_id: int | None = Form(default=None),
):
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated account is missing its database identifier.",
        )
    if action not in {"save", "submit"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported course-plan action.",
        )

    result = CoursePlanService(CoursePlanRepository(db)).validate_and_save(
        user_id=user.id,
        target_semester=target_semester,
        selected_course_codes=selected_course_codes or [],
        submit=action == "submit",
        plan_id=edit_plan_id,
    )
    if result.submission_limit_reached:
        flash(request, result.errors[0], "danger")
        return RedirectResponse(
            url=request.url_for("course_plan_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if result.submitted:
        return RedirectResponse(
            url=request.url_for("progress_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return templates.TemplateResponse(
        request=request,
        name="course-plan.html",
        context={
            "user": user,
            "plan": result.plan_page,
            "page_errors": result.errors,
            "editing_plan_id": edit_plan_id,
        },
        status_code=(
            status.HTTP_422_UNPROCESSABLE_ENTITY if result.has_errors else status.HTTP_200_OK
        ),
    )


@router.post(
    "/course-plan/{plan_id}/withdraw",
    name="course_plan_withdraw",
)
async def course_plan_withdraw(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    plan_id: int,
):
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated account is missing its database identifier.",
        )
    result = CoursePlanService(CoursePlanRepository(db)).withdraw_submitted_plan(
        user_id=user.id,
        plan_id=plan_id,
    )
    flash(
        request,
        result.message,
        "success" if result.succeeded else "danger",
    )
    return RedirectResponse(
        url=request.url_for("course_plan_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/course-plan/{plan_id}/delete",
    name="course_plan_delete_draft",
)
async def course_plan_delete_draft(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    plan_id: int,
):
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated account is missing its database identifier.",
        )
    result = CoursePlanService(CoursePlanRepository(db)).delete_saved_draft(
        user_id=user.id,
        plan_id=plan_id,
    )
    flash(
        request,
        result.message,
        "success" if result.succeeded else "danger",
    )
    return RedirectResponse(
        url=request.url_for("course_plan_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
