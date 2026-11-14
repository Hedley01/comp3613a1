from sqlmodel import SQLModel

class SigninRequest(SQLModel):
    username: str
    password: str

class SignupRequest(SQLModel):
    username: str
    email: str
    password: str

VALID_USERS = {"bob": "bobpass", "admin": "adminpass"}

def authenticate (username, password):
    return username in VALID_USERS and VALID_USERS[username] == password
