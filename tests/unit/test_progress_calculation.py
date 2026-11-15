from types import SimpleNamespace

import pytest

from app.services.progress_service import ProgressService


def course(code, credits, title=None):
    return SimpleNamespace(
        course_code=code, title=title or f"Course {code}", credits=credits
    )


def make_records(*, total_credits, completed=(), current=(), remaining=()):
   
    return SimpleNamespace(
        student=SimpleNamespace(first_name="Bob", last_name="Student"),
        degree=SimpleNamespace(
            title="BSc Computer Science", total_required_credits=total_credits
        ),
        completed_courses=[
            (course(f"DONE {i}", credits), SimpleNamespace(semester_taken="Sem 1", grade="A"))
            for i, credits in enumerate(completed)
        ],
        current_courses=[
            (SimpleNamespace(target_semester=semester), course(code, credits))
            for code, credits, semester in current
        ],
        remaining_courses=[
            course(f"TODO {i}", credits) for i, credits in enumerate(remaining)
        ],
    )


class FakeProgressRepository:
    def __init__(self, records=None, student=None):
        self.records = records
        self.student = student
        self.requested_student_ids = []

    def get_student_by_user_id(self, user_id):
        return self.student

    def get_progress_records(self, student_id):
        self.requested_student_ids.append(student_id)
        return self.records


def calculate(records):
    return ProgressService(FakeProgressRepository(records)).calculate_progress(1)


def test_earned_credits_are_the_sum_of_completed_course_credits():
    progress = calculate(make_records(total_credits=30, completed=[3, 3, 6]))

    assert progress["earned_credits"] == 12
    assert progress["total_required_credits"] == 30
    assert progress["remaining_credits"] == 18
    assert progress["progress_percent"] == 40.0


def test_progress_percent_is_rounded_to_one_decimal_place():
    progress = calculate(make_records(total_credits=9, completed=[3]))

    assert progress["progress_percent"] == 33.3


@pytest.mark.parametrize(
    "remaining_credits, expected_semesters",
    [(0, 0), (1, 1), (15, 1), (16, 2), (30, 2), (31, 3)],
)
def test_semesters_remaining_assumes_15_credits_per_semester(
    remaining_credits, expected_semesters
):
    progress = calculate(make_records(total_credits=remaining_credits))

    assert progress["remaining_credits"] == remaining_credits
    assert progress["estimated_semesters_remaining"] == expected_semesters


def test_remaining_credits_never_go_negative_and_percent_caps_at_100():
    progress = calculate(make_records(total_credits=6, completed=[9]))

    assert progress["earned_credits"] == 9
    assert progress["remaining_credits"] == 0
    assert progress["progress_percent"] == 100.0


def test_zero_required_credits_does_not_divide_by_zero():
    progress = calculate(make_records(total_credits=0, completed=[3]))

    assert progress["progress_percent"] == 0
    assert progress["remaining_credits"] == 0


def test_current_courses_are_listed_but_do_not_count_as_earned():
    progress = calculate(
        make_records(
            total_credits=12,
            completed=[3],
            current=[("CSCI 102", 3, "Semester 2")],
        )
    )

    assert progress["earned_credits"] == 3
    assert progress["current_courses"] == [
        {
            "course_code": "CSCI 102",
            "title": "Course CSCI 102",
            "credits": 3,
            "target_semester": "Semester 2",
        }
    ]


def test_progress_includes_student_and_degree_details():
    progress = calculate(make_records(total_credits=12, completed=[3]))

    assert progress["student_name"] == "Bob Student"
    assert progress["degree_title"] == "BSc Computer Science"
    assert len(progress["completed_courses"]) == 1
    assert progress["completed_courses"][0]["grade"] == "A"


def test_no_progress_when_account_has_no_student_profile():
    service = ProgressService(FakeProgressRepository(student=None))

    assert service.calculate_progress_for_user_id(user_id=99) is None


def test_no_progress_when_student_records_are_missing():
    assert calculate(None) is None


def test_progress_for_user_looks_up_the_students_own_id():
    repo = FakeProgressRepository(
        records=make_records(total_credits=12, completed=[3]),
        student=SimpleNamespace(student_id=7),
    )

    progress = ProgressService(repo).calculate_progress_for_user_id(user_id=3)

    assert progress is not None
    assert repo.requested_student_ids == [7]
