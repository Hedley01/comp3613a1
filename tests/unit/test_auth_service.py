from types import SimpleNamespace

import jwt
import pytest

from app.config import get_settings
from app.services.auth_service import AuthService
from app.utilities.security import encrypt_password, verify_password

ACCOUNTS = [
    ("bob", "bobpass", "regular_user"),
    ("admin", "adminpass", "admin"),
    ("advisor", "advisorpass", "advisor"),
]


class FakeUserRepository:
   
    def __init__(self, users):
        self.users = {user.username: user for user in users}
        self.created = []

    def get_by_username(self, username):
        return self.users.get(username)

    def create(self, user_data):
        self.created.append(user_data)
        return user_data


@pytest.fixture(scope="module")
def users():
    # Hashing is slow on purpose, so hash once per module.
    return {
        username: SimpleNamespace(
            id=index,
            username=username,
            password=encrypt_password(password),
            role=role,
        )
        for index, (username, password, role) in enumerate(ACCOUNTS, start=1)
    }


@pytest.fixture()
def repo(users):
    return FakeUserRepository(users.values())


@pytest.fixture()
def service(repo):
    return AuthService(repo)


def decode(token):
    settings = get_settings()
    return jwt.decode(
        token, settings.secret_key, algorithms=[settings.jwt_algorithm]
    )


@pytest.mark.parametrize("username, password, role", ACCOUNTS)
def test_valid_credentials_return_a_token_for_that_user(
    service, users, username, password, role
):
    token = service.authenticate_user(username, password)

    assert isinstance(token, str)
    claims = decode(token)
    assert claims["sub"] == str(users[username].id)
    assert claims["role"] == role
    assert "exp" in claims


@pytest.mark.parametrize(
    "username, password",
    [
        ("bob", "wrongpass"),     # right user, wrong password
        ("admin", "bobpass"),     # another user's password
        ("nobody", "bobpass"),    # unknown user
        ("bob", "BOBPASS"),       # passwords are case sensitive
        ("bob", ""),              # empty password
    ],
)
def test_invalid_credentials_do_not_authenticate(service, username, password):
    assert service.authenticate_user(username, password) is None


def test_stored_passwords_are_hashed_not_plaintext(users):
    for username, password, _ in ACCOUNTS:
        assert users[username].password != password


def test_hash_verifies_only_the_original_password():
    hashed = encrypt_password("s3cret-pass")

    assert hashed != "s3cret-pass"
    assert verify_password("s3cret-pass", hashed) is True
    assert verify_password("S3CRET-PASS", hashed) is False


def test_same_password_hashes_differently_each_time():
    # Salted hashes: two hashes of one password must not be identical.
    assert encrypt_password("repeat-me") != encrypt_password("repeat-me")


def test_register_user_stores_a_hashed_password_and_regular_user_role(
    service, repo
):
    service.register_user("newbie", "newbie@example.com", "plain-text-pw")

    created = repo.created[0]
    assert created.username == "newbie"
    assert created.email == "newbie@example.com"
    assert created.role == "regular_user"
    assert created.password != "plain-text-pw"
    assert verify_password("plain-text-pw", created.password) is True
