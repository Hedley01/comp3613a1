from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.cli import _seed_demo_progress
from app.models import (
    Advisor,
    CompletedCourse,
    Course,
    CoursePlan,
    CoursePlanCourse,
    CoursePrerequisite,
    Degree,
    DegreeCourse,
    DegreeElectiveCourse,
    Student,
    User,
)
from app.repositories.course_plan import CoursePlanRepository
from app.repositories.progress import ProgressRepository
from app.services.course_plan_service import CoursePlanService
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
        ongoing = Course(
            course_code="CSCI 103",
            title="Software Design",
            credits=3,
            description="Approved ongoing course.",
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
        session.add_all([required, remaining, ongoing, elective, student])
        session.flush()
        approved_plan = CoursePlan(
            student_id=student.student_id,
            target_semester="Semester 1",
            status="approved",
        )
        session.add(approved_plan)
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
                DegreeCourse(
                    degree_id=degree.degree_id,
                    course_code=ongoing.course_code,
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
                CoursePlanCourse(
                    plan_id=approved_plan.plan_id,
                    course_code=ongoing.course_code,
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
        assert progress["current_courses"] == [
            {
                "course_code": "CSCI 103",
                "title": "Software Design",
                "credits": 3,
                "target_semester": "Semester 1",
            }
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
        advisor_user = User(
            username="advisor",
            email="advisor@example.com",
            password="hashed-password",
            role="advisor",
        )
        second_advisor_user = User(
            username="advisor-two",
            email="advisor-two@example.com",
            password="hashed-password",
            role="advisor",
        )
        session.add_all([advisor_user, second_advisor_user])
        session.commit()
        session.refresh(advisor_user)
        session.refresh(second_advisor_user)

        assert _seed_demo_progress(
            session,
            user.email,
            user.id,
            [advisor_user.id, second_advisor_user.id],
        ) is True
        advisor_profile = session.exec(
            select(Advisor).where(Advisor.user_id == advisor_user.id)
        ).one()
        assert _seed_demo_progress(
            session,
            user.email,
            user.id,
            [advisor_user.id, second_advisor_user.id],
        ) is False
        seeded_student = session.exec(
            select(Student).where(Student.auth_user_id == user.id)
        ).one()
        assert seeded_student.advisor_id == advisor_profile.advisor_id

        progress = ProgressService(
            ProgressRepository(session)
        ).calculate_progress_for_user_id(user.id)
        student_count = len(session.exec(select(Student)).all())
        elective_count = len(session.exec(select(DegreeElectiveCourse)).all())

    assert progress is not None
    assert progress["earned_credits"] == 63
    assert progress["total_required_credits"] == 96
    assert progress["remaining_credits"] == 33
    assert progress["estimated_semesters_remaining"] == 3
    assert len(progress["completed_courses"]) == 21
    assert len(progress["remaining_courses"]) == 11
    assert student_count == 1
    assert elective_count == 3


def test_course_plan_submission_stays_draft_until_prerequisites_are_completed():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(
            username="plan-student",
            email="plan-student@example.com",
            password="hashed-password",
            role="regular_user",
        )
        advisor = Advisor(
            first_name="Alex",
            last_name="Morgan",
            department="Computer Science",
        )
        degree = Degree(title="BSc Computer Science", total_required_credits=6)
        prerequisite = Course(
            course_code="CSCI 201",
            title="Programming I",
            credits=3,
            description="Intro to programming.",
        )
        advanced = Course(
            course_code="CSCI 202",
            title="Programming II",
            credits=3,
            description="Advanced programming.",
        )
        elective = Course(
            course_code="CSCI 203",
            title="Approved Elective",
            credits=3,
            description="Faculty-approved elective.",
        )
        session.add_all([user, advisor, degree, prerequisite, advanced, elective])
        session.flush()
        student = Student(
            first_name="Casey",
            last_name="Student",
            email="plan-student@example.com",
            auth_user_id=user.id,
            advisor_id=advisor.advisor_id,
            degree_id=degree.degree_id,
        )
        session.add(student)
        session.flush()
        session.add_all(
            [
                DegreeCourse(
                    degree_id=degree.degree_id,
                    course_code=prerequisite.course_code,
                ),
                DegreeCourse(
                    degree_id=degree.degree_id,
                    course_code=advanced.course_code,
                ),
                CoursePrerequisite(
                    course_code=advanced.course_code,
                    prerequisite_code=prerequisite.course_code,
                ),
                DegreeElectiveCourse(
                    degree_id=degree.degree_id,
                    course_code=elective.course_code,
                ),
            ]
        )
        session.commit()
        service = CoursePlanService(CoursePlanRepository(session))

        invalid_semester = service.validate_and_save(
            user_id=user.id,
            target_semester="Fall 2026",
            selected_course_codes=[advanced.course_code],
            submit=True,
        )
        assert invalid_semester.has_errors
        assert invalid_semester.plan_page is not None
        assert invalid_semester.plan_page["target_semester"] == "Semester 1"

        blocked = service.validate_and_save(
            user_id=user.id,
            target_semester="Semester 1",
            selected_course_codes=[advanced.course_code],
            submit=True,
        )

        assert blocked.has_errors
        assert not blocked.submitted
        assert blocked.plan_page is not None
        assert [course["course_code"] for course in blocked.plan_page["elective_courses"]] == [
            elective.course_code
        ]
        assert blocked.plan_page["selected_course_codes"] == [advanced.course_code]
        assert "CSCI 201 (Programming I)" in blocked.plan_page["course_errors"][
            advanced.course_code
        ][0]
        saved_plan = session.exec(select(CoursePlan)).one()
        assert saved_plan.status == "draft"
        assert saved_plan.submission_date is None
        assert session.exec(select(CoursePlanCourse)).one().course_code == "CSCI 202"
        original_plan_id = saved_plan.plan_id
        draft_history = service.get_plan_page(user_id=user.id)
        assert draft_history.plan_page is not None
        assert draft_history.plan_page["plan_history"][0]["status"] == "draft"
        reopened_draft = service.get_editable_plan_page(
            user_id=user.id,
            plan_id=original_plan_id,
        )
        assert reopened_draft.plan_page is not None
        assert reopened_draft.plan_page["editable_plan_id"] == original_plan_id
        assert reopened_draft.plan_page["editable_plan_status"] == "draft"
        assert reopened_draft.plan_page["target_semester"] == "Semester 1"
        assert reopened_draft.plan_page["selected_course_codes"] == [
            advanced.course_code
        ]

        moved_draft = service.validate_and_save(
            user_id=user.id,
            target_semester="Semester 2",
            selected_course_codes=[advanced.course_code],
            submit=False,
        )
        assert moved_draft.has_errors
        assert session.exec(select(CoursePlan)).all()[0].plan_id == original_plan_id
        assert session.exec(select(CoursePlan)).one().target_semester == "Semester 2"
        assert len(session.exec(select(CoursePlan)).all()) == 1

        session.add(
            CompletedCourse(
                student_id=student.student_id,
                course_code=prerequisite.course_code,
                semester_taken="Spring 2026",
                grade="A",
            )
        )
        session.commit()
        submitted = service.validate_and_save(
            user_id=user.id,
            target_semester="Semester 1",
            selected_course_codes=[advanced.course_code, elective.course_code],
            submit=True,
        )

        assert submitted.submitted
        updated_plan = session.exec(select(CoursePlan)).one()
        assert updated_plan.status == "submitted"
        assert updated_plan.submission_date is not None
        assert {
            item.course_code for item in session.exec(select(CoursePlanCourse)).all()
        } == {advanced.course_code, elective.course_code}

        student_plan = service.get_plan_page(user_id=user.id)
        assert student_plan.plan_page is not None
        assert student_plan.plan_page["plan_history"] == [
            {
                "plan_id": updated_plan.plan_id,
                "target_semester": "Semester 1",
                "status": "submitted",
                "submission_date": updated_plan.submission_date,
                "advisor_feedback": "",
                "courses": [
                    {"course_code": advanced.course_code, "title": advanced.title},
                    {"course_code": elective.course_code, "title": elective.title},
                ],
            }
        ]
        assert advanced.course_code not in {
            course["course_code"]
            for course in student_plan.plan_page["catalog_courses"]
        }
        assert elective.course_code not in {
            course["course_code"]
            for course in student_plan.plan_page["elective_courses"]
        }

        additional_course = Course(
            course_code="CSCI 204",
            title="Software Testing",
            credits=3,
            description="Testing fundamentals.",
        )
        next_semester_course = Course(
            course_code="CSCI 205",
            title="Systems Programming",
            credits=3,
            description="Systems programming fundamentals.",
        )
        summer_course = Course(
            course_code="CSCI 206",
            title="Cloud Computing",
            credits=3,
            description="Cloud computing fundamentals.",
        )
        session.add_all([additional_course, next_semester_course, summer_course])
        session.flush()
        session.add_all(
            [
                DegreeCourse(
                    degree_id=degree.degree_id,
                    course_code=additional_course.course_code,
                ),
                DegreeCourse(
                    degree_id=degree.degree_id,
                    course_code=next_semester_course.course_code,
                ),
                DegreeCourse(
                    degree_id=degree.degree_id,
                    course_code=summer_course.course_code,
                ),
            ]
        )
        session.commit()

        second_semester_submission = service.validate_and_save(
            user_id=user.id,
            target_semester="Semester 2",
            selected_course_codes=[additional_course.course_code],
            submit=True,
        )
        assert second_semester_submission.submitted

        blocked_duplicate_semester = service.validate_and_save(
            user_id=user.id,
            target_semester="Semester 2",
            selected_course_codes=[next_semester_course.course_code],
            submit=True,
        )
        assert blocked_duplicate_semester.submission_limit_reached
        assert not blocked_duplicate_semester.submitted
        assert blocked_duplicate_semester.plan_page is not None
        assert blocked_duplicate_semester.plan_page["selected_course_codes"] == [
            next_semester_course.course_code
        ]
        saved_plans = session.exec(
            select(CoursePlan).order_by(CoursePlan.plan_id)
        ).all()
        assert [item.status for item in saved_plans] == [
            "submitted",
            "submitted",
            "draft",
        ]
        draft_plan_id = saved_plans[2].plan_id

        deleted_draft = service.delete_saved_draft(
            user_id=user.id,
            plan_id=draft_plan_id,
        )
        assert deleted_draft.succeeded
        assert session.get(CoursePlan, draft_plan_id) is None
        assert session.exec(
            select(CoursePlanCourse).where(
                CoursePlanCourse.plan_id == draft_plan_id
            )
        ).all() == []

        summer_submission = service.validate_and_save(
            user_id=user.id,
            target_semester="Summer Semester",
            selected_course_codes=[summer_course.course_code],
            submit=True,
        )
        assert summer_submission.submitted
        assert len(session.exec(select(CoursePlan)).all()) == 3

        another_user = User(
            username="another-student",
            email="another-student@example.com",
            password="test-password",
            role="regular_user",
        )
        session.add(another_user)
        session.flush()
        another_student = Student(
            first_name="Another",
            last_name="Student",
            email="another-student@example.com",
            auth_user_id=another_user.id,
            degree_id=degree.degree_id,
        )
        session.add(another_student)
        session.commit()
        updated_plan.status = "approved"
        session.add(updated_plan)
        session.commit()

        cannot_withdraw = service.withdraw_submitted_plan(
            user_id=another_user.id,
            plan_id=updated_plan.plan_id,
        )
        assert not cannot_withdraw.succeeded
        assert session.get(CoursePlan, updated_plan.plan_id).status == "approved"

        withdrawn = service.withdraw_submitted_plan(
            user_id=user.id,
            plan_id=updated_plan.plan_id,
        )
        assert withdrawn.succeeded
        assert session.get(CoursePlan, updated_plan.plan_id).status == "withdrawn"
        withdrawn_history = service.get_plan_page(user_id=user.id)
        assert withdrawn_history.plan_page is not None
        withdrawn_entry = next(
            item
            for item in withdrawn_history.plan_page["plan_history"]
            if item["plan_id"] == updated_plan.plan_id
        )
        assert withdrawn_entry["status"] == "withdrawn"
        assert advanced.course_code in {
            course["course_code"]
            for course in withdrawn_history.plan_page["catalog_courses"]
        }

        editable_approved_plan = service.get_editable_plan_page(
            user_id=user.id,
            plan_id=updated_plan.plan_id,
        )
        assert editable_approved_plan.plan_page is not None
        assert editable_approved_plan.plan_page["selected_course_codes"] == [
            advanced.course_code,
            elective.course_code,
        ]
        resubmitted = service.validate_and_save(
            user_id=user.id,
            target_semester="Semester 1",
            selected_course_codes=[advanced.course_code, elective.course_code],
            submit=True,
            plan_id=updated_plan.plan_id,
        )
        assert resubmitted.submitted
        assert session.get(CoursePlan, updated_plan.plan_id).status == "submitted"
        final_plans = session.exec(
            select(CoursePlan).order_by(CoursePlan.target_semester)
        ).all()
        assert len(final_plans) == 3
        assert {
            (plan.target_semester, plan.status) for plan in final_plans
        } == {
            ("Semester 1", "submitted"),
            ("Semester 2", "submitted"),
            ("Summer Semester", "submitted"),
        }
