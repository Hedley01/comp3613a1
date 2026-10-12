from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.cli import _seed_demo_progress
from app.models import (
    Advisor,
    CompletedCourse,
    Course,
    Degree,
    DegreeCourse,
    Student,
    User,
)
from app.repositories.progress import ProgressRepository
from app.services.progress_service import ProgressService


def test_progress_is_calculated_from_required_completed_courses():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            username="student",
            email="student@example.com",
            password="hashed-password",
            role="regular_user",
        )
        advisor = Advisor(
            first_name="Alex",
            last_name="Morgan",
            department="Computer Science",
        )
        degree = Degree(title="BSc Computer Science", total_required_credits=9)
        session.add_all([user, advisor, degree])
        session.flush()

        required = Course(
            course_code="CSCI 101",
            title="Programming Fundamentals",
            credits=3,
            description="Introductory programming.",
        )
        remaining = Course(
            course_code="CSCI 102",
            title="Data Structures",
            credits=6,
            description="Core data structures.",
        )
        elective = Course(
            course_code="MATH 101",
            title="Calculus",
            credits=3,
            description="Calculus elective.",
        )
        student = Student(
            first_name="Taylor",
            last_name="Student",
            email="student@example.com",
            auth_user_id=user.id,
            advisor_id=advisor.advisor_id,
            degree_id=degree.degree_id,
        )
        session.add_all([required, remaining, elective, student])
        session.flush()
        session.add_all(
            [
                DegreeCourse(
                    degree_id=degree.degree_id,
                    course_code=required.course_code,
                ),
                DegreeCourse(
                    degree_id=degree.degree_id,
                    course_code=remaining.course_code,
                ),
                CompletedCourse(
                    student_id=student.student_id,
                    course_code=required.course_code,
                    semester_taken="Fall 2025",
                    grade="A",
                ),
                CompletedCourse(
                    student_id=student.student_id,
                    course_code=elective.course_code,
                    semester_taken="Spring 2026",
                    grade="B",
                ),
            ]
        )
        session.commit()

        progress = ProgressService(
            ProgressRepository(session)
        ).calculate_progress_for_user_id(user.id)

        assert progress is not None
        assert progress["student_name"] == "Taylor Student"
        assert progress["degree_title"] == "BSc Computer Science"
        assert progress["earned_credits"] == 3
        assert progress["total_required_credits"] == 9
        assert progress["remaining_credits"] == 6
        assert progress["estimated_semesters_remaining"] == 1
        assert progress["progress_percent"] == 33.3
        assert [course["course_code"] for course in progress["completed_courses"]] == [
            "CSCI 101"
        ]
        assert [course["course_code"] for course in progress["remaining_courses"]] == [
            "CSCI 102"
        ]


def test_progress_is_unavailable_without_a_linked_student():
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            username="new-student",
            email="new-student@example.com",
            password="hashed-password",
            role="regular_user",
        )
        session.add(user)
        session.commit()

        progress = ProgressService(
            ProgressRepository(session)
        ).calculate_progress_for_user_id(user.id)

    assert progress is None


def test_demo_seed_provides_the_wireframed_progress_and_is_idempotent():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            username="bob",
            email="bob@example.com",
            password="hashed-password",
            role="regular_user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        assert user.id is not None
        assert _seed_demo_progress(session, user.email, user.id) is True
        assert _seed_demo_progress(session, user.email, user.id) is False

        progress = ProgressService(
            ProgressRepository(session)
        ).calculate_progress_for_user_id(user.id)
        student_count = len(session.exec(select(Student)).all())

    assert progress is not None
    assert progress["earned_credits"] == 63
    assert progress["total_required_credits"] == 96
    assert progress["remaining_credits"] == 33
    assert progress["estimated_semesters_remaining"] == 3
    assert len(progress["completed_courses"]) == 21
    assert len(progress["remaining_courses"]) == 11
    assert student_count == 1
