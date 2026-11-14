import pytest

def test_user_authentication():
  valid_users = {
    "bob": "bobpass",
    "admin" : "adminpass"
  }

  username = "bob"
  password = "bobpass"
  assert username in valid_users
  assert valid_users[username] == password

  invalid_pass = "wrongpass"
  assert valid_users["bob"] != invalid_pass

def test_credit_calculations():
  
  
    
def test_plan_status_transitions():

