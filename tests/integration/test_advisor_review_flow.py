import pytest

MIDDLE_DOT = "\u00b7"


@pytest.fixture()
def submitted_plan_id(make_client, load_plans):
    
    student = make_client("bob")
    response = student.post(
        "/course-plan",
        data={
            "target_semester": "Semester 1",
            "selected_course_codes": ["CSCI 102"],
            "action": "submit",
        },
    )
    assert response.status_code == 303
    [plan] = load_plans()
    assert plan["status"] == "submitted"
    return plan["plan_id"]


def decide(client, plan_id, decision, feedback=""):
    return client.post(
        f"/advisor/reviews/{plan_id}",
        data={"decision": decision, "feedback": feedback},
    )


def test_pending_plan_appears_in_the_assigned_advisors_inbox(
    make_client, submitted_plan_id
):
    advisor = make_client("advisor")

    response = advisor.get("/advisor/reviews")

    assert response.status_code == 200
    assert "Bob Student" in response.text
    assert "BSc Computer Science" in response.text
    assert "Programming II" in response.text


def test_plan_does_not_appear_in_another_advisors_inbox(make_client, submitted_plan_id):
    other_advisor = make_client("advisor2")

    response = other_advisor.get("/advisor/reviews")

    assert response.status_code == 200
    assert "Bob Student" not in response.text
    assert "All caught up" in response.text


def test_advisor_approval_updates_the_plan_and_the_students_progress(
    make_client, load_plans, submitted_plan_id
):
    student = make_client("bob")
    advisor = make_client("advisor")
    assert f"CSCI 102 {MIDDLE_DOT} Semester 1" not in student.get("/progress").text

    response = decide(advisor, submitted_plan_id, "approve", "Looks good.")

    assert response.status_code == 303
    [plan] = load_plans()
    assert plan["status"] == "approved"
    assert plan["feedback"] == "Looks good."
    # Approved courses show up as current courses on the student's progress page.
    assert f"CSCI 102 {MIDDLE_DOT} Semester 1" in student.get("/progress").text
    # the plan has left the advisor's pending queue.
    assert "Bob Student" not in advisor.get("/advisor/reviews").text


def test_revision_request_reaches_the_student_who_can_resubmit(
    make_client, load_plans, submitted_plan_id
):
    student = make_client("bob")
    advisor = make_client("advisor")

    response = decide(
        advisor, submitted_plan_id, "request_revisions", "Swap CSCI 102 for CSCI 110."
    )

    assert response.status_code == 303
    [plan] = load_plans()
    assert plan["status"] == "revision_requested"
    assert plan["feedback"] == "Swap CSCI 102 for CSCI 110."
    # The student sees the feedback on the editable plan
    assert "Swap CSCI 102 for CSCI 110." in student.get("/course-plan").text
    #  its corrected and resubmited through the normal validation step.
    resubmit = student.post(
        "/course-plan",
        data={
            "target_semester": "Semester 1",
            "selected_course_codes": ["CSCI 110"],
            "action": "submit",
        },
    )
    assert resubmit.status_code == 303
    [plan] = load_plans()
    assert plan["status"] == "submitted"
    assert plan["courses"] == ["CSCI 110"]
    assert plan["feedback"] == ""                   


def test_revision_request_without_feedback_is_rejected(
    make_client, load_plans, submitted_plan_id
):
    advisor = make_client("advisor")

    response = decide(advisor, submitted_plan_id, "request_revisions", "   ")

    assert response.status_code == 303
    assert load_plans()[0]["status"] == "submitted"


def test_student_cannot_approve_their_own_plan(
    make_client, load_plans, submitted_plan_id
):
    student = make_client("bob")

    response = decide(student, submitted_plan_id, "approve")

    assert response.status_code == 403
    assert load_plans()[0]["status"] == "submitted"


def test_admin_cannot_approve_a_plan(make_client, load_plans, submitted_plan_id):
    admin = make_client("admin")

    response = decide(admin, submitted_plan_id, "approve")

    assert response.status_code == 403
    assert load_plans()[0]["status"] == "submitted"


def test_advisor_cannot_approve_another_advisors_student_plan(
    make_client, load_plans, submitted_plan_id
):
    other_advisor = make_client("advisor2")

    response = decide(other_advisor, submitted_plan_id, "approve")

    assert response.status_code == 303              
    assert load_plans()[0]["status"] == "submitted"


def test_anonymous_visitor_cannot_approve_a_plan(
    make_client, load_plans, submitted_plan_id
):
    anonymous = make_client()

    response = decide(anonymous, submitted_plan_id, "approve")

    assert "Session Expired" in response.text
    assert load_plans()[0]["status"] == "submitted"
