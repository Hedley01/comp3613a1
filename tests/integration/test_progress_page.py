def test_student_sees_their_seeded_degree_progress(make_client):
    client = make_client("bob")

    response = client.get("/progress")

    assert response.status_code == 200
    html = response.text
    assert "BSc Computer Science" in html
    assert "Bob Student" in html
    assert "of 12 credits earned" in html     
    assert "9 credits to go" in html
    assert "Discrete Mathematics" in html     


def test_account_without_a_student_profile_sees_the_empty_state(make_client):
    client = make_client("admin")

    response = client.get("/progress")

    assert response.status_code == 200
    assert "student record linked to admin@example.com" in response.text
