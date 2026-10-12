from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    Advisor,
    Course,
    CoursePlan,
    CoursePlanCourse,
    Degree,
    Student,
    User,
)
from app.repositories.advisor_assignment import AdvisorAssignmentRepository
from app.repositories.advisor_reviews import AdvisorReviewRepository
from app.repositories.course_plan import CoursePlanRepository
from app.services.advisor_assignment_service import AdvisorAssignmentService
from app.services.advisor_review_service import AdvisorReviewService
from app.services.course_plan_service import CoursePlanService


def _review_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    advisor_user = User(
        username="advisor",
        email="advisor@example.com",
        password="hashed-password",
        role="advisor",
    )
    other_advisor_user = User(
        username="other-advisor",
        email="other-advisor@example.com",
        password="hashed-password",
        role="advisor",
    )
    student_user = User(
        username="student",
        email="student@example.com",
        password="hashed-password",
        role="regular_user",
    )
    degree = Degree(title="BSc Computer Science", total_required_credits=3)
    course = Course(
        course_code="CSCI 301",
        title="Software Architecture",
        credits=3,
        description="Architecture fundamentals.",
    )
    session.add_all(
        [advisor_user, other_advisor_user, student_user, degree, course]
    )
    session.flush()

    advisor = Advisor(
        first_name="Alex",
        last_name="Morgan",
        department="Computer Science",
        user_id=advisor_user.id,
    )
    other_advisor = Advisor(
        first_name="Jordan",
        last_name="Lee",
        department="Computer Science",
        user_id=other_advisor_user.id,
    )
    session.add_all([advisor, other_advisor])
    session.flush()

    student = Student(
        first_name="Casey",
        last_name="Student",
        email="student@example.com",
        auth_user_id=student_user.id,
        advisor_id=advisor.advisor_id,
        degree_id=degree.degree_id,
    )
    session.add(student)
    session.flush()
    plan = CoursePlan(
        student_id=student.student_id,
        advisor_id=advisor.advisor_id,
        target_semester="Semester 1",
        status="submitted",
    )
    other_plan = CoursePlan(
        student_id=student.student_id,
        advisor_id=other_advisor.advisor_id,
        target_semester="Semester 2",
        status="submitted",
    )
    session.add_all([plan, other_plan])
    session.flush()
    session.add_all(
        [
            CoursePlanCourse(
                plan_id=plan.plan_id,
                course_code=course.course_code,
            ),
            CoursePlanCourse(
                plan_id=other_plan.plan_id,
                course_code=course.course_code,
            ),
        ]
    )
    session.commit()
    service = AdvisorReviewService(AdvisorReviewRepository(session))
    return session, service, advisor_user, student_user, plan, other_plan


def test_inbox_shows_only_plans_assigned_to_the_signed_in_advisor():
    session, service, advisor_user, _, plan, other_plan = _review_fixture()
    try:
        inbox = service.get_inbox(advisor_user.id)

        assert inbox.error is None
        assert inbox.advisor_name == "Alex Morgan"
        assert [item.plan.plan_id for item in inbox.pending_plans] == [
            plan.plan_id
        ]
        assert inbox.selected_plan is not None
        assert inbox.selected_plan.student.first_name == "Casey"
        assert inbox.selected_plan.degree.title == "BSc Computer Science"
        assert [course.course_code for course in inbox.selected_plan.courses] == [
            "CSCI 301"
        ]
        assert other_plan.plan_id not in {
            item.plan.plan_id for item in inbox.pending_plans
        }
    finally:
        session.close()


def test_requesting_revisions_requires_feedback_and_returns_plan_to_student():
    session, service, advisor_user, student_user, plan, _ = _review_fixture()
    try:
        missing_feedback = service.review_plan(
            user_id=advisor_user.id,
            plan_id=plan.plan_id,
            decision="request_revisions",
            feedback="  ",
        )
        assert not missing_feedback.succeeded
        assert session.get(CoursePlan, plan.plan_id).status == "submitted"

        result = service.review_plan(
            user_id=advisor_user.id,
            plan_id=plan.plan_id,
            decision="request_revisions",
            feedback="Please choose a different course.",
        )

        updated = session.get(CoursePlan, plan.plan_id)
        assert result.succeeded
        assert updated.status == "revision_requested"
        assert updated.advisor_feedback == "Please choose a different course."
        assert service.get_inbox(advisor_user.id).pending_plans == []
        student_plan = CoursePlanService(
            CoursePlanRepository(session)
        ).get_plan_page(
            user_id=student_user.id,
            target_semester="Semester 1",
        )
        assert student_plan.plan_page is not None
        assert (
            student_plan.plan_page["advisor_feedback"]
            == "Please choose a different course."
        )
    finally:
        session.close()


def test_advisor_can_approve_only_a_plan_in_their_own_queue():
    session, service, advisor_user, _, plan, other_plan = _review_fixture()
    try:
        not_assigned = service.review_plan(
            user_id=advisor_user.id,
            plan_id=other_plan.plan_id,
            decision="approve",
            feedback="",
        )
        assert not not_assigned.succeeded
        assert session.get(CoursePlan, other_plan.plan_id).status == "submitted"

        approved = service.review_plan(
            user_id=advisor_user.id,
            plan_id=plan.plan_id,
            decision="approve",
            feedback="Looks good.",
        )

        updated = session.exec(
            select(CoursePlan).where(CoursePlan.plan_id == plan.plan_id)
        ).one()
        assert approved.succeeded
        assert updated.status == "approved"
        assert updated.advisor_feedback == "Looks good."
    finally:
        session.close()


def test_advisor_can_withdraw_owned_pending_plan_without_erasing_history():
    session, service, advisor_user, student_user, plan, _ = _review_fixture()
    try:
        result = service.withdraw_plan(
            user_id=advisor_user.id,
            plan_id=plan.plan_id,
        )

        withdrawn = session.get(CoursePlan, plan.plan_id)
        assert result.succeeded
        assert withdrawn.status == "withdrawn"
        assert (
            session.exec(
                select(CoursePlanCourse).where(CoursePlanCourse.plan_id == plan.plan_id)
            )
            .one()
            .course_code
            == "CSCI 301"
        )
        assert service.get_inbox(advisor_user.id).pending_plans == []

        student_plan = CoursePlanService(
            CoursePlanRepository(session)
        ).get_plan_page(user_id=student_user.id)
        assert student_plan.plan_page is not None
        withdrawn_history = next(
            item
            for item in student_plan.plan_page["plan_history"]
            if item["plan_id"] == plan.plan_id
        )
        assert withdrawn_history["status"] == "withdrawn"
    finally:
        session.close()


def test_advisor_cannot_withdraw_another_advisors_submission():
    session, service, advisor_user, _, _, other_plan = _review_fixture()
    try:
        result = service.withdraw_plan(
            user_id=advisor_user.id,
            plan_id=other_plan.plan_id,
        )

        assert not result.succeeded
        assert session.get(CoursePlan, other_plan.plan_id).status == "submitted"
    finally:
        session.close()


def test_new_student_assignment_chooses_the_least_loaded_advisor():
    session, _, advisor_user, _, _, _ = _review_fixture()
    try:
        assigned = AdvisorAssignmentService(
            AdvisorAssignmentRepository(session)
        ).get_least_loaded_advisor()

        assert assigned.user_id != advisor_user.id
    finally:
        session.close()
