from dataclasses import dataclass
from typing import TypedDict

from app.repositories.course_plan import CatalogCourse, CoursePlanRepository

TARGET_SEMESTERS = ("Semester 1", "Semester 2", "Summer Semester")


class CatalogCourseData(TypedDict):
    course_code: str
    title: str
    credits: int
    description: str
    prerequisites: list[dict[str, str]]


class CoursePlanPageData(TypedDict):
    target_semester: str
    catalog_courses: list[CatalogCourseData]
    elective_courses: list[CatalogCourseData]
    selected_courses: list[CatalogCourseData]
    selected_course_codes: list[str]
    errors: list[str]
    course_errors: dict[str, list[str]]
    advisor_feedback: str


@dataclass
class CoursePlanResult:
    has_errors: bool
    errors: list[str]
    plan_page: CoursePlanPageData | None
    submitted: bool = False


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

    def get_plan_page(
        self,
        *,
        user_id: int,
        target_semester: str | None = None,
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

        semester = target_semester or TARGET_SEMESTERS[0]
        if semester not in TARGET_SEMESTERS:
            semester = TARGET_SEMESTERS[0]
        editable_plan, saved_course_codes = self.course_plan_repo.get_plan(
            student.student_id, semester
        )
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
        catalog = self.course_plan_repo.get_catalog(
            student.degree_id, completed_codes
        )
        catalog_data = [self._course_data(entry) for entry in catalog]
        elective_catalog = self.course_plan_repo.get_elective_catalog(
            student.degree_id, completed_codes
        )
        elective_data = [self._course_data(entry) for entry in elective_catalog]
        by_code = {
            entry["course_code"]: entry
            for entry in [*catalog_data, *elective_data]
        }
        valid_selected_codes = [code for code in codes if code in by_code]

        page: CoursePlanPageData = {
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
        }
        return CoursePlanResult(
            has_errors=bool(errors),
            errors=errors or [],
            plan_page=page,
        )

    def validate_and_save(
        self,
        *,
        user_id: int,
        target_semester: str,
        selected_course_codes: list[str],
        submit: bool,
    ) -> CoursePlanResult:
        student = self.course_plan_repo.get_student_for_user(user_id)
        if student is None or student.student_id is None:
            return CoursePlanResult(
                has_errors=True,
                errors=["There is no student profile linked to your account."],
                plan_page=None,
            )

        semester = target_semester.strip()
        course_codes = list(dict.fromkeys(selected_course_codes))
        errors: list[str] = []
        course_errors: dict[str, list[str]] = {}
        if semester not in TARGET_SEMESTERS:
            errors.append("Choose a valid target semester.")

        completed_codes = self.course_plan_repo.get_completed_course_codes(
            student.student_id
        )
        catalog = self.course_plan_repo.get_catalog(
            student.degree_id, completed_codes
        )
        elective_catalog = self.course_plan_repo.get_elective_catalog(
            student.degree_id, completed_codes
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


        if submit and not errors and not course_errors:
            self.course_plan_repo.save_plan(
                student=student,
                target_semester=semester,
                course_codes=valid_codes,
                submit=True,
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
            )

        result = self.get_plan_page(
            user_id=user_id,
            target_semester=semester if semester in TARGET_SEMESTERS else None,
            selected_course_codes=valid_codes,
            errors=[],
            course_errors=course_errors,
        )
        result.has_errors = bool(errors or course_errors)
        result.errors = errors
        if (
            not submit
            and not errors
            and not course_errors
            and result.plan_page is not None
        ):
            result.plan_page["errors"] = ["Draft saved."]
        return result
