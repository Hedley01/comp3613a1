from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.models 
from app.database import get_session
from app.main import app
from app.models import (
    Advisor,
    CompletedCourse,
    Course,
    CoursePlan,
    CoursePlanCourse,
    CoursePrerequisite,
    Degree,
    DegreeCourse,
    Student,
    User,
)
from app.utilities.security import encrypt_password

ACCOUNTS = {
    "bob": ("bobpass", "regular_user"),
    "admin": ("adminpass", "admin"),
    "advisor": ("advisorpass", "advisor"),
    "advisor2": ("advisorpass2", "advisor"),
}
 
HASHES = {name: encrypt_password(password) for name, (password, _) in ACCOUNTS.items()}


@pytest.fixture()
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded(engine):
    with Session(engine) as session:
        users = {
            name: User(
                username=name,
                email=f"{name}@example.com",
                password=HASHES[name],
                role=role,
            )
            for name, (_, role) in ACCOUNTS.items()
        }
        degree = Degree(title="BSc Computer Science", total_required_credits=12)
        courses = [
            Course(course_code="CSCI 101", title="Programming I", credits=3, description="Intro."),
            Course(course_code="CSCI 102", title="Programming II", credits=3, description="Next."),
            Course(course_code="CSCI 103", title="Programming III", credits=3, description="Advanced."),
            Course(course_code="CSCI 110", title="Discrete Mathematics", credits=3, description="Maths."),
        ]
        session.add_all([*users.values(), degree, *courses])
        session.flush()

        alex = Advisor(
            first_name="Alex",
            last_name="Morgan",
            department="Computer Science",
            user_id=users["advisor"].id,
        )
        jordan = Advisor(
            first_name="Jordan",
            last_name="Lee",
            department="Computer Science",
            user_id=users["advisor2"].id,
        )
        session.add_all([alex, jordan])
        session.flush()

        student = Student(
            first_name="Bob",
            last_name="Student",
            email="bob@example.com",
            auth_user_id=users["bob"].id,
            advisor_id=alex.advisor_id,
            degree_id=degree.degree_id,
        )
        session.add(student)
        session.flush()

        session.add_all(
            [
                *[
                    DegreeCourse(degree_id=degree.degree_id, course_code=c.course_code)
                    for c in courses
                ],
                CoursePrerequisite(course_code="CSCI 102", prerequisite_code="CSCI 101"),
                CoursePrerequisite(course_code="CSCI 103", prerequisite_code="CSCI 102"),
                CompletedCourse(
                    student_id=student.student_id,
                    course_code="CSCI 101",
                    semester_taken="Semester 1 2025",
                    grade="A",
                ),
            ]
        )
        session.commit()
        return SimpleNamespace(
            student_id=student.student_id,
            advisor_id=alex.advisor_id,
            other_advisor_id=jordan.advisor_id,
        )


@pytest.fixture()
def make_client(engine, seeded):
  

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    clients = []

    def _make(username=None):
      
        client = TestClient(app, follow_redirects=False)
        clients.append(client)
        if username is not None:
            password, _ = ACCOUNTS[username]
            response = client.post(
                "/login", data={"username": username, "password": password}
            )
            assert response.status_code == 303, f"login failed for {username}"
            assert client.cookies.get("access_token"), "no access_token cookie set"
        return client

    yield _make

    app.dependency_overrides.clear()
    for client in clients:
        client.close()


@pytest.fixture()
def load_plans(engine):

    def _load():
        with Session(engine) as session:
            plans = session.exec(select(CoursePlan).order_by(CoursePlan.plan_id)).all()
            result = []
            for plan in plans:
                codes = session.exec(
                    select(CoursePlanCourse.course_code)
                    .where(CoursePlanCourse.plan_id == plan.plan_id)
                    .order_by(CoursePlanCourse.course_code)
                ).all()
                result.append(
                    {
                        "plan_id": plan.plan_id,
                        "student_id": plan.student_id,
                        "advisor_id": plan.advisor_id,
                        "semester": plan.target_semester,
                        "status": plan.status,
                        "feedback": plan.advisor_feedback,
                        "submission_date": plan.submission_date,
                        "courses": list(codes),
                    }
                )
            return result

    return _load
