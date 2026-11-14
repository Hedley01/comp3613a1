def post_plan(client, codes, *, semester="Semester 1", action="submit"):
    return client.post(
        "/course-plan",
        data={
            "target_semester": semester,
            "selected_course_codes": codes,
            "action": action,
        },
    )


def test_course_plan_page_lists_the_courses_the_student_can_pick(make_client):
    client = make_client("bob")

    response = client.get("/course-plan")

    assert response.status_code == 200
    assert "Programming II" in response.text        # prerequisite CSCI 101 is done
    assert "Discrete Mathematics" in response.text


def test_valid_plan_is_submitted_and_assigned_to_the_students_advisor(
    make_client, load_plans, seeded
):
    client = make_client("bob")

    response = post_plan(client, ["CSCI 102"])

    assert response.status_code == 303
    assert response.headers["location"].endswith("/progress")
    [plan] = load_plans()
    assert plan["status"] == "submitted"
    assert plan["semester"] == "Semester 1"
    assert plan["courses"] == ["CSCI 102"]
    assert plan["advisor_id"] == seeded.advisor_id
    assert plan["submission_date"] is not None


def test_unmet_prerequisite_blocks_submission_and_keeps_a_draft(
    make_client, load_plans
):
    client = make_client("bob")

    response = post_plan(client, ["CSCI 103"])     # needs CSCI 102, not yet done

    assert response.status_code == 422
    assert "Requires completed prerequisite" in response.text
    assert "CSCI 102 (Programming II)" in response.text
    [plan] = load_plans()
    assert plan["status"] == "draft"
    assert plan["submission_date"] is None


def test_saving_a_draft_does_not_submit_it(make_client, load_plans):
    client = make_client("bob")

    response = post_plan(client, ["CSCI 102"], action="save")

    assert response.status_code == 200
    assert "Draft saved" in response.text
    [plan] = load_plans()
    assert plan["status"] == "draft"
    assert plan["courses"] == ["CSCI 102"]


def test_second_submission_for_the_same_semester_is_blocked(make_client, load_plans):
    client = make_client("bob")
    assert post_plan(client, ["CSCI 102"]).status_code == 303

    response = post_plan(client, ["CSCI 110"])     # same semester again

    assert response.status_code == 303
    assert response.headers["location"].endswith("/course-plan")
    statuses = [plan["status"] for plan in load_plans()]
    assert statuses == ["submitted", "draft"]       # only one plan is submitted


def test_a_different_semester_can_have_its_own_submitted_plan(make_client, load_plans):
    client = make_client("bob")
    assert post_plan(client, ["CSCI 102"], semester="Semester 1").status_code == 303

    response = post_plan(client, ["CSCI 110"], semester="Semester 2")

    assert response.status_code == 303
    assert [p["status"] for p in load_plans()] == ["submitted", "submitted"]


def test_student_can_withdraw_a_submitted_plan(make_client, load_plans):
    client = make_client("bob")
    post_plan(client, ["CSCI 102"])
    [plan] = load_plans()

    response = client.post(f"/course-plan/{plan['plan_id']}/withdraw")

    assert response.status_code == 303
    [plan] = load_plans()
    assert plan["status"] == "withdrawn"
    assert plan["courses"] == ["CSCI 102"]          # kept in history


def test_student_can_delete_a_saved_draft(make_client, load_plans):
    client = make_client("bob")
    post_plan(client, ["CSCI 102"], action="save")
    [plan] = load_plans()

    response = client.post(f"/course-plan/{plan['plan_id']}/delete")

    assert response.status_code == 303
    assert load_plans() == []


def test_course_plan_page_requires_login(make_client):
    client = make_client()

    response = client.get("/course-plan")

    assert "Session Expired" in response.text
