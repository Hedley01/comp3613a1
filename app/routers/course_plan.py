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

from . import router, templates


@router.get("/course-plan", response_class=HTMLResponse, name="course_plan_view")
async def course_plan_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    target_semester: str | None = None,
):
    if user.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authenticated account is missing its database identifier.",
        )
    plan_result = CoursePlanService(CoursePlanRepository(db)).get_plan_page(
        user_id=user.id,
        target_semester=target_semester or TARGET_SEMESTERS[0],
    )
    return templates.TemplateResponse(
        request=request,
        name="course-plan.html",
        context={
            "user": user,
            "plan": plan_result.plan_page,
            "page_errors": plan_result.errors,
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
        },
        status_code=(
            status.HTTP_422_UNPROCESSABLE_ENTITY if result.has_errors else status.HTTP_200_OK
        ),
    )
