from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.academic import (
    Advisor,
    Course,
    CoursePlan,
    CoursePlanCourse,
    Degree,
    Student,
)


@dataclass
class ReviewCourse:
    course_code: str
    title: str
    credits: int


@dataclass
class PendingCoursePlan:
    plan: CoursePlan
    student: Student
    degree: Degree
    courses: list[ReviewCourse]


class AdvisorReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_advisor_for_user(self, user_id: int) -> Advisor | None:
        return self.db.exec(
            select(Advisor).where(Advisor.user_id == user_id)
        ).one_or_none()

    def get_pending_plans(self, advisor_id: int) -> list[PendingCoursePlan]:
        plan_rows = self.db.exec(
            select(CoursePlan, Student, Degree)
            .join(Student, Student.student_id == CoursePlan.student_id)
            .join(Degree, Degree.degree_id == Student.degree_id)
            .where(
                CoursePlan.advisor_id == advisor_id,
                CoursePlan.status == "submitted",
            )
            .order_by(
                CoursePlan.submission_date,
                CoursePlan.plan_id,
            )
        ).all()
        if not plan_rows:
            return []

        plan_ids = [
            plan.plan_id for plan, _, _ in plan_rows if plan.plan_id is not None
        ]
        course_rows = self.db.exec(
            select(
                CoursePlanCourse.plan_id,
                Course.course_code,
                Course.title,
                Course.credits,
            )
            .join(Course, Course.course_code == CoursePlanCourse.course_code)
            .where(CoursePlanCourse.plan_id.in_(plan_ids))
            .order_by(Course.course_code)
        ).all()
        courses_by_plan: dict[int, list[ReviewCourse]] = {
            plan_id: []             for plan_id in plan_ids
        }
        for plan_id, course_code, title, credits in course_rows:
            courses_by_plan[plan_id].append(
                ReviewCourse(
                    course_code=course_code,
                    title=title,
                    credits=credits,
                )
            )

        return [
            PendingCoursePlan(
                plan=plan,
                student=student,
                degree=degree,
                courses=courses_by_plan[plan.plan_id],
            )
            for plan, student, degree in plan_rows
            if plan.plan_id is not None
        ]

    def get_reviewable_plan(
        self, *, plan_id: int, advisor_id: int
    ) -> CoursePlan | None:
        return self.db.exec(
            select(CoursePlan).where(
                CoursePlan.plan_id == plan_id,
                CoursePlan.advisor_id == advisor_id,
                CoursePlan.status == "submitted",
            )
        ).one_or_none()

    def save_decision(
        self, *, plan: CoursePlan, status: str, feedback: str
    ) -> None:
        plan.status = status
        plan.advisor_feedback = feedback
        self.db.add(plan)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def withdraw_plan(self, *, plan: CoursePlan) -> None:
        plan.status = "withdrawn"
        self.db.add(plan)
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
