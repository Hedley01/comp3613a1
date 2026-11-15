from types import SimpleNamespace

import pytest

from app.services.advisor_review_service import AdvisorReviewService
from app.services.course_plan_service import TARGET_SEMESTERS, CoursePlanService


def catalog_entry(code, title, prerequisites=()):
    return SimpleNamespace(
        course=SimpleNamespace(
            course_code=code,
            title=title,
            credits=3,
            description=f"{title} description",
        ),
        prerequisites=list(prerequisites),
    )


class FakeCoursePlanRepository:

    def __init__(self, *, has_student=True, completed=(), has_submitted_plan=False):
        self.student = (
            SimpleNamespace(student_id=1, degree_id=1, advisor_id=5)
            if has_student
            else None
        )
        self.completed = set(completed)
        self.has_submitted_plan = has_submitted_plan
        self.catalog = [
            catalog_entry("CSCI 101", "Programming I"),
            catalog_entry(
                "CSCI 102", "Programming II", [("CSCI 101", "Programming I")]
            ),
        ]
        self.saved = []  # every save_plan() call, in order

    def get_student_for_user(self, user_id):
        return self.student

    def get_completed_course_codes(self, student_id):
        return set(self.completed)

    def get_committed_course_codes(self, student_id):
        return set()

    def get_catalog(self, degree_id, excluded_codes):
        return [
            entry
            for entry in self.catalog
            if entry.course.course_code not in excluded_codes
        ]

    def get_elective_catalog(self, degree_id, excluded_codes):
        return []

    def has_active_submitted_plan(self, student_id, target_semester):
        return self.has_submitted_plan

    def get_editable_plan(self, student_id):
        return None, []

    def get_plan_history(self, student_id):
        return []

    def save_plan(self, *, student, target_semester, course_codes, submit, plan_id=None):
        self.saved.append(
            {
                "semester": target_semester,
                "courses": list(course_codes),
                "status": "submitted" if submit else "draft",
            }
        )


def run(repo, codes, *, submit, semester="Semester 1"):
    return CoursePlanService(repo).validate_and_save(
        user_id=1,
        target_semester=semester,
        selected_course_codes=codes,
        submit=submit,
    )


def test_target_semesters_offered_to_students():
    assert TARGET_SEMESTERS == ("Semester 1", "Semester 2", "Summer Semester")


def test_saving_without_submitting_keeps_the_plan_as_a_draft():
    repo = FakeCoursePlanRepository()

    result = run(repo, ["CSCI 101"], submit=False)

    assert not result.submitted
    assert not result.has_errors
    assert repo.saved == [
        {"semester": "Semester 1", "courses": ["CSCI 101"], "status": "draft"}
    ]
    assert result.plan_page["errors"] == ["Draft saved."]


def test_valid_plan_moves_from_draft_to_submitted():
    repo = FakeCoursePlanRepository()

    result = run(repo, ["CSCI 101"], submit=True)

    assert result.submitted
    assert not result.has_errors
    assert [save["status"] for save in repo.saved] == ["submitted"]


def test_unmet_prerequisite_blocks_submission_and_leaves_a_draft():
    repo = FakeCoursePlanRepository(completed=[])

    result = run(repo, ["CSCI 102"], submit=True)

    assert not result.submitted
    assert result.has_errors
    assert "CSCI 101 (Programming I)" in result.plan_page["course_errors"]["CSCI 102"][0]
    assert [save["status"] for save in repo.saved] == ["draft"]


def test_same_plan_submits_once_the_prerequisite_is_completed():
    repo = FakeCoursePlanRepository(completed=["CSCI 101"])

    result = run(repo, ["CSCI 102"], submit=True)

    assert result.submitted
    assert [save["status"] for save in repo.saved] == ["submitted"]


def test_selecting_the_prerequisite_in_the_same_plan_does_not_satisfy_it():
    repo = FakeCoursePlanRepository(completed=[])

    result = run(repo, ["CSCI 101", "CSCI 102"], submit=True)

    assert not result.submitted
    assert "CSCI 102" in result.plan_page["course_errors"]


def test_empty_plan_cannot_be_submitted():
    repo = FakeCoursePlanRepository()

    result = run(repo, [], submit=True)

    assert not result.submitted
    assert "Add at least one available course before submitting." in result.errors


def test_course_outside_the_degree_cannot_be_submitted():
    repo = FakeCoursePlanRepository()

    result = run(repo, ["MATH 999"], submit=True)

    assert not result.submitted
    assert any("not available for your degree" in error for error in result.errors)


def test_invalid_semester_is_rejected_and_nothing_is_saved():
    repo = FakeCoursePlanRepository()

    result = run(repo, ["CSCI 101"], submit=True, semester="Fall 2030")

    assert not result.submitted
    assert "Choose a valid target semester." in result.errors
    assert repo.saved == []


def test_second_submission_for_the_same_semester_is_blocked():
    repo = FakeCoursePlanRepository(has_submitted_plan=True)

    result = run(repo, ["CSCI 101"], submit=True)

    assert result.submission_limit_reached
    assert not result.submitted
    assert "Semester 1" in result.errors[0]
    assert [save["status"] for save in repo.saved] == ["draft"]


def test_account_without_a_student_profile_cannot_plan():
    repo = FakeCoursePlanRepository(has_student=False)

    result = run(repo, ["CSCI 101"], submit=True)

    assert result.has_errors
    assert result.plan_page is None
    assert repo.saved == []

class FakeAdvisorReviewRepository:
    """In-memory stand-in for AdvisorReviewRepository holding one plan."""

    ADVISOR_ID = 5

    def __init__(self, *, plan_status="submitted", plan_advisor_id=5, linked=True):
        self.advisor = (
            SimpleNamespace(
                advisor_id=self.ADVISOR_ID, first_name="Alex", last_name="Morgan"
            )
            if linked
            else None
        )
        self.plan = SimpleNamespace(
            plan_id=10,
            advisor_id=plan_advisor_id,
            status=plan_status,
            advisor_feedback="",
        )

    def get_advisor_for_user(self, user_id):
        return self.advisor

    def get_reviewable_plan(self, *, plan_id, advisor_id):
        plan = self.plan
        if (
            plan.plan_id == plan_id
            and plan.advisor_id == advisor_id
            and plan.status == "submitted"
        ):
            return plan
        return None

    def save_decision(self, *, plan, status, feedback):
        plan.status = status
        plan.advisor_feedback = feedback

    def withdraw_plan(self, *, plan):
        plan.status = "withdrawn"


def review(repo, decision, feedback=""):
    return AdvisorReviewService(repo).review_plan(
        user_id=1, plan_id=10, decision=decision, feedback=feedback
    )


def test_advisor_approval_moves_plan_from_submitted_to_approved():
    repo = FakeAdvisorReviewRepository()

    result = review(repo, "approve", "Looks good.")

    assert result.succeeded
    assert repo.plan.status == "approved"
    assert repo.plan.advisor_feedback == "Looks good."


def test_requesting_revisions_moves_plan_to_revision_requested_with_feedback():
    repo = FakeAdvisorReviewRepository()

    result = review(repo, "request_revisions", "  Please pick another course.  ")

    assert result.succeeded
    assert repo.plan.status == "revision_requested"
    assert repo.plan.advisor_feedback == "Please pick another course."


@pytest.mark.parametrize("feedback", ["", "   "])
def test_requesting_revisions_without_feedback_is_rejected(feedback):
    repo = FakeAdvisorReviewRepository()

    result = review(repo, "request_revisions", feedback)

    assert not result.succeeded
    assert repo.plan.status == "submitted"


def test_unknown_decision_is_rejected():
    repo = FakeAdvisorReviewRepository()

    result = review(repo, "reject")

    assert not result.succeeded
    assert repo.plan.status == "submitted"


def test_feedback_longer_than_2000_characters_is_rejected():
    repo = FakeAdvisorReviewRepository()

    result = review(repo, "request_revisions", "x" * 2001)

    assert not result.succeeded
    assert repo.plan.status == "submitted"


def test_advisor_cannot_review_a_plan_assigned_to_another_advisor():
    repo = FakeAdvisorReviewRepository(plan_advisor_id=99)

    result = review(repo, "approve")

    assert not result.succeeded
    assert repo.plan.status == "submitted"


def test_a_plan_that_is_already_approved_cannot_be_reviewed_again():
    repo = FakeAdvisorReviewRepository(plan_status="approved")

    result = review(repo, "request_revisions", "Changed my mind.")

    assert not result.succeeded
    assert repo.plan.status == "approved"


def test_account_without_an_advisor_profile_cannot_review():
    repo = FakeAdvisorReviewRepository(linked=False)

    result = review(repo, "approve")

    assert not result.succeeded
    assert repo.plan.status == "submitted"


def test_advisor_can_withdraw_a_pending_submission():
    repo = FakeAdvisorReviewRepository()

    result = AdvisorReviewService(repo).withdraw_plan(user_id=1, plan_id=10)

    assert result.succeeded
    assert repo.plan.status == "withdrawn"
