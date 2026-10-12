from dataclasses import dataclass
from datetime import date
from typing import TypedDict

from app.repositories.course_plan import (
    CatalogCourse,
    CoursePlanRepository,
    StudentPlanHistory,
)

TARGET_SEMESTERS = ("Semester 1", "Semester 2", "Summer Semester")


class CatalogCourseData(TypedDict):
    course_code: str
    title: str
    credits: int
    description: str
    prerequisites: list[dict[str, str]]


class PlanHistoryCourseData(TypedDict):
    course_code: str
    title: str


class PlanHistoryEntryData(TypedDict):
    plan_id: int
    target_semester: str
    status: str
    submission_date: date | None
    advisor_feedback: str
    courses: list[PlanHistoryCourseData]


class CoursePlanPageData(TypedDict):
    editable_plan_id: int | None
    editable_plan_status: str | None
    target_semester: str
    catalog_courses: list[CatalogCourseData]
    elective_courses: list[CatalogCourseData]
    selected_courses: list[CatalogCourseData]
    selected_course_codes: list[str]
    errors: list[str]
    course_errors: dict[str, list[str]]
    advisor_feedback: str
    plan_history: list[PlanHistoryEntryData]


@dataclass
class CoursePlanResult:
    has_errors: bool
    errors: list[str]
    plan_page: CoursePlanPageData | None
    submitted: bool = False
    submission_limit_reached: bool = False


@dataclass
class StudentPlanActionResult:
    succeeded: bool
    message: str


class CoursePlanService:
    def __init__(self, course_plan_repo: CoursePlanRepository):
        self.course_plan_repo = course_plan_repo

    @staticmethod
    def _course_data(entry: CatalogCourse) -> CatalogCourseData:
        return {
            "course_code": entry.course.course_code,
            "title": entry.course.title,
            "credits": entry.course.credits,
            "description": entry.course.description,
            "prerequisites": [
                {"course_code": code, "title": title}
                for code, title in entry.prerequisites
            ],
        }

    @staticmethod
    def _history_data(entry: StudentPlanHistory) -> PlanHistoryEntryData:
        plan = entry.plan
        if plan.plan_id is None:
            raise ValueError("Course plan is missing its database identifier.")
        return {
            "plan_id": plan.plan_id,
            "target_semester": plan.target_semester,
            "status": plan.status,
            "submission_date": plan.submission_date,
            "advisor_feedback": plan.advisor_feedback,
            "courses": [
                {"course_code": course_code, "title": title}
                for course_code, title in entry.courses
            ],
        }

    def get_plan_page(
        self,
        *,
        user_id: int,
        target_semester: str | None = None,
        selected_course_codes: list[str] | None = None,
        errors: list[str] | None = None,
        course_errors: dict[str, list[str]] | None = None,
    ) -> CoursePlanResult:
        return self._build_plan_page(
            user_id=user_id,
            target_semester=target_semester,
            selected_course_codes=selected_course_codes,
            errors=errors,
            course_errors=course_errors,
        )

    def get_editable_plan_page(
        self, *, user_id: int, plan_id: int
    ) -> CoursePlanResult:
        return self._build_plan_page(
            user_id=user_id,
            edit_plan_id=plan_id,
        )

    def _build_plan_page(
        self,
        *,
        user_id: int,
        target_semester: str | None = None,
        edit_plan_id: int | None = None,
        selected_course_codes: list[str] | None = None,
        errors: list[str] | None = None,
        course_errors: dict[str, list[str]] | None = None,
    ) -> CoursePlanResult:
        student = self.course_plan_repo.get_student_for_user(user_id)
        if student is None or student.student_id is None:
            return CoursePlanResult(
                has_errors=True,
                errors=["There is no student profile linked to your account."],
                plan_page=None,
            )

        if edit_plan_id is None:
            editable_plan, saved_course_codes = (
                self.course_plan_repo.get_editable_plan(student.student_id)
            )
        else:
            editable_plan, saved_course_codes = (
                self.course_plan_repo.get_editable_plan_by_id(
                    student.student_id, edit_plan_id
                )
            )
            if (
                editable_plan is not None
                and editable_plan.status == "withdrawn"
                and self.course_plan_repo.has_other_editable_plan(
                    student.student_id, edit_plan_id
                )
            ):
                editable_plan = None
            if editable_plan is None:
                errors = [
                    *(errors or []),
                    (
                        "That plan cannot be edited while another draft is active. "
                        "Delete or submit the other draft first."
                    ),
                ]
        semester = (
            editable_plan.target_semester
            if editable_plan is not None
            else target_semester or TARGET_SEMESTERS[0]
        )
        if semester not in TARGET_SEMESTERS:
            semester = TARGET_SEMESTERS[0]
        codes = list(
            dict.fromkeys(
                saved_course_codes
                if selected_course_codes is None
                else selected_course_codes
            )
        )
        completed_codes = self.course_plan_repo.get_completed_course_codes(
            student.student_id
        )
        unavailable_codes = completed_codes | (
            self.course_plan_repo.get_committed_course_codes(student.student_id)
        )
        catalog = self.course_plan_repo.get_catalog(
            student.degree_id, unavailable_codes
        )
        catalog_data = [self._course_data(entry) for entry in catalog]
        elective_catalog = self.course_plan_repo.get_elective_catalog(
            student.degree_id, unavailable_codes
        )
        elective_data = [self._course_data(entry) for entry in elective_catalog]
        by_code = {
            entry["course_code"]: entry
            for entry in [*catalog_data, *elective_data]
        }
        valid_selected_codes = [code for code in codes if code in by_code]

        page: CoursePlanPageData = {
            "editable_plan_id": (
                editable_plan.plan_id if editable_plan is not None else None
            ),
            "editable_plan_status": (
                editable_plan.status if editable_plan is not None else None
            ),
            "target_semester": semester,
            "catalog_courses": catalog_data,
            "elective_courses": elective_data,
            "selected_courses": [by_code[code] for code in valid_selected_codes],
            "selected_course_codes": valid_selected_codes,
            "errors": errors or [],
            "course_errors": course_errors or {},
            "advisor_feedback": (
                editable_plan.advisor_feedback if editable_plan is not None else ""
            ),
            "plan_history": [
                self._history_data(entry)
                for entry in self.course_plan_repo.get_plan_history(student.student_id)
            ],
        }
        return CoursePlanResult(
            has_errors=bool(errors),
            errors=errors or [],
            plan_page=page,
        )

    def withdraw_submitted_plan(
        self, *, user_id: int, plan_id: int
    ) -> StudentPlanActionResult:
        student = self.course_plan_repo.get_student_for_user(user_id)
        if student is None or student.student_id is None:
            return StudentPlanActionResult(
                succeeded=False,
                message="There is no student profile linked to your account.",
            )

        plan = self.course_plan_repo.get_withdrawable_plan(
            student_id=student.student_id,
            plan_id=plan_id,
        )
        if plan is None:
            return StudentPlanActionResult(
                succeeded=False,
                message="This submitted or approved plan is not available to withdraw.",
            )

        self.course_plan_repo.withdraw_plan(plan=plan)
        return StudentPlanActionResult(
            succeeded=True,
            message=(
                "Plan withdrawn. You can edit it from your submissions and resubmit it."
            ),
        )

    def delete_saved_draft(
        self, *, user_id: int, plan_id: int
    ) -> StudentPlanActionResult:
        student = self.course_plan_repo.get_student_for_user(user_id)
        if student is None or student.student_id is None:
            return StudentPlanActionResult(
                succeeded=False,
                message="There is no student profile linked to your account.",
            )

        deleted = self.course_plan_repo.delete_saved_draft(
            student_id=student.student_id,
            plan_id=plan_id,
        )
        if not deleted:
            return StudentPlanActionResult(
                succeeded=False,
                message="Only your saved drafts can be deleted.",
            )
        return StudentPlanActionResult(
            succeeded=True,
            message="Saved draft deleted.",
        )

    def validate_and_save(
        self,
        *,
        user_id: int,
        target_semester: str,
        selected_course_codes: list[str],
        submit: bool,
        plan_id: int | None = None,
    ) -> CoursePlanResult:
        student = self.course_plan_repo.get_student_for_user(user_id)
        if student is None or student.student_id is None:
            return CoursePlanResult(
                has_errors=True,
                errors=["There is no student profile linked to your account."],
                plan_page=None,
            )

        if plan_id is not None:
            editable_plan, _ = self.course_plan_repo.get_editable_plan_by_id(
                student.student_id, plan_id
            )
            if editable_plan is None or (
                editable_plan.status == "withdrawn"
                and self.course_plan_repo.has_other_editable_plan(
                    student.student_id, plan_id
                )
            ):
                message = (
                    "That plan cannot be edited while another draft is active. "
                    "Delete or submit the other draft first."
                )
                page_result = self._build_plan_page(
                    user_id=user_id,
                    errors=[message],
                )
                page_result.has_errors = True
                return page_result

        semester = target_semester.strip()
        course_codes = list(dict.fromkeys(selected_course_codes))
        errors: list[str] = []
        course_errors: dict[str, list[str]] = {}
        if semester not in TARGET_SEMESTERS:
            errors.append("Choose a valid target semester.")

        completed_codes = self.course_plan_repo.get_completed_course_codes(
            student.student_id
        )
        unavailable_codes = completed_codes | (
            self.course_plan_repo.get_committed_course_codes(student.student_id)
        )
        catalog = self.course_plan_repo.get_catalog(
            student.degree_id, unavailable_codes
        )
        elective_catalog = self.course_plan_repo.get_elective_catalog(
            student.degree_id, unavailable_codes
        )
        catalog_by_code = {
            entry.course.course_code: entry for entry in catalog
        }
        catalog_by_code.update(
            {entry.course.course_code: entry for entry in elective_catalog}
        )
        invalid_codes = [code for code in course_codes if code not in catalog_by_code]
        if invalid_codes:
            errors.append(
                "Some selected courses are not available for your degree: "
                + ", ".join(invalid_codes)
            )
        valid_codes = [code for code in course_codes if code in catalog_by_code]
        if submit and not valid_codes:
            errors.append("Add at least one available course before submitting.")

        for course_code in valid_codes:
            course = catalog_by_code[course_code]
            missing = [
                (prerequisite_code, prerequisite_title)
                for prerequisite_code, prerequisite_title in course.prerequisites
                if prerequisite_code not in completed_codes
            ]
            if missing:
                details = ", ".join(
                    f"{prerequisite_code} ({prerequisite_title})"
                    for prerequisite_code, prerequisite_title in missing
                )
                course_errors[course_code] = [
                    f"Requires completed prerequisite(s): {details}."
                ]


        submission_limit_reached = False
        if (
            submit
            and not errors
            and not course_errors
            and self.course_plan_repo.has_active_submitted_plan(
                student.student_id, semester
            )
        ):
            errors.append(
                f"A plan for {semester} has already been submitted or approved. "
                "Withdraw it before submitting another plan for that semester."
            )
            submission_limit_reached = True

        if submit and not errors and not course_errors:
            self.course_plan_repo.save_plan(
                student=student,
                target_semester=semester,
                course_codes=valid_codes,
                submit=True,
                plan_id=plan_id,
            )
            return CoursePlanResult(
                has_errors=False,
                errors=[],
                plan_page=None,
                submitted=True,
            )

        if semester in TARGET_SEMESTERS:
            self.course_plan_repo.save_plan(
                student=student,
                target_semester=semester,
                course_codes=valid_codes,
                submit=False,
                plan_id=plan_id,
            )

        result = self._build_plan_page(
            user_id=user_id,
            target_semester=semester if semester in TARGET_SEMESTERS else None,
            edit_plan_id=plan_id,
            selected_course_codes=valid_codes,
            errors=[],
            course_errors=course_errors,
        )
        result.has_errors = bool(errors or course_errors)
        result.errors = errors
        result.submission_limit_reached = submission_limit_reached
        if (
            not submit
            and not errors
            and not course_errors
            and result.plan_page is not None
        ):
            result.plan_page["errors"] = ["Draft saved."]
        return result
