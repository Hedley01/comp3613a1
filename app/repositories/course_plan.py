from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, delete, select

from app.models.academic import (
    CompletedCourse,
    Course,
    CoursePlan,
    CoursePlanCourse,
    CoursePrerequisite,
    DegreeCourse,
    DegreeElectiveCourse,
    Student,
)


@dataclass
class CatalogCourse:
    course: Course
    prerequisites: list[tuple[str, str]]


class CoursePlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_student_for_user(self, user_id: int) -> Student | None:
        return self.db.exec(
            select(Student).where(Student.auth_user_id == user_id)
        ).one_or_none()

    def get_completed_course_codes(self, student_id: int) -> set[str]:
        return set(
            self.db.exec(
                select(CompletedCourse.course_code).where(
                    CompletedCourse.student_id == student_id
                )
            ).all()
        )

    def get_catalog(self, degree_id: int, excluded_codes: set[str]) -> list[CatalogCourse]:
        statement = (
            select(Course)
            .join(DegreeCourse, DegreeCourse.course_code == Course.course_code)
            .where(DegreeCourse.degree_id == degree_id)
            .order_by(Course.course_code)
        )
        courses = self.db.exec(statement).all()
        catalog = [
            course for course in courses if course.course_code not in excluded_codes
        ]
        return self._add_prerequisites(catalog)

    def get_elective_catalog(
        self, degree_id: int, excluded_codes: set[str]
    ) -> list[CatalogCourse]:
        courses = self.db.exec(
            select(Course)
            .join(
                DegreeElectiveCourse,
                DegreeElectiveCourse.course_code == Course.course_code,
            )
            .where(DegreeElectiveCourse.degree_id == degree_id)
            .order_by(Course.course_code)
        ).all()
        catalog = [
            course for course in courses if course.course_code not in excluded_codes
        ]
        return self._add_prerequisites(catalog)

    def _add_prerequisites(self, courses: list[Course]) -> list[CatalogCourse]:
        catalog_codes = {course.course_code for course in courses}
        if not catalog_codes:
            return []
        prerequisites = self.db.exec(
            select(CoursePrerequisite, Course.title)
            .join(
                Course,
                Course.course_code == CoursePrerequisite.prerequisite_code,
            )
            .where(CoursePrerequisite.course_code.in_(catalog_codes))
            .order_by(CoursePrerequisite.course_code, Course.course_code)
        ).all()
        by_course: dict[str, list[tuple[str, str]]] = {
            course_code: [] for course_code in catalog_codes
        }
        for prerequisite, prerequisite_title in prerequisites:
            by_course[prerequisite.course_code].append(
                (prerequisite.prerequisite_code, prerequisite_title)
            )
        return [
            CatalogCourse(course=course, prerequisites=by_course[course.course_code])
            for course in courses
        ]

    def get_plan(
        self, student_id: int, target_semester: str
    ) -> tuple[CoursePlan | None, list[str]]:
        plan = self.db.exec(
            select(CoursePlan)
            .where(
                CoursePlan.student_id == student_id,
                CoursePlan.target_semester == target_semester,
                CoursePlan.status.in_(("draft", "revision_requested")),
            )
            .order_by(CoursePlan.plan_id.desc())
        ).first()
        if plan is None or plan.plan_id is None:
            return plan, []

        course_codes = self.db.exec(
            select(CoursePlanCourse.course_code)
            .where(CoursePlanCourse.plan_id == plan.plan_id)
            .order_by(CoursePlanCourse.course_code)
        ).all()
        return plan, list(course_codes)

    def save_plan(
        self,
        *,
        student: Student,
        target_semester: str,
        course_codes: list[str],
        submit: bool,
    ) -> CoursePlan:
        if student.student_id is None:
            raise ValueError("Student profile is missing its database identifier.")

        plan, _ = self.get_plan(student.student_id, target_semester)
        if plan is None:
            plan = CoursePlan(
                student_id=student.student_id,
                advisor_id=student.advisor_id,
                target_semester=target_semester,
                status="draft",
            )
            self.db.add(plan)
            self.db.flush()
        if plan.plan_id is None:
            raise ValueError("Course plan is missing its database identifier.")

        self.db.exec(
            delete(CoursePlanCourse).where(
                CoursePlanCourse.plan_id == plan.plan_id
            )
        )
        self.db.flush()
        for course_code in course_codes:
            self.db.add(
                CoursePlanCourse(
                    plan_id=plan.plan_id,
                    course_code=course_code,
                )
            )

        plan.status = "submitted" if submit else "draft"
        plan.submission_date = (
            datetime.now(timezone.utc).date() if submit else None
        )
        plan.advisor_feedback = ""
        self.db.add(plan)
        try:
            self.db.commit()
            self.db.refresh(plan)
        except Exception:
            self.db.rollback()
            raise
        return plan
