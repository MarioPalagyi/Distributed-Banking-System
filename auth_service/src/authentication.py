import base64
import os
import time
from usermodels import users, UserRole

# in-memory token storage
active_tokens = {}
TOKEN_EXP = 3600

class AuthorizationError(Exception):
    """For raising authorisation error in the authenticate function"""
    pass

def generate_token(username, userrole):
    """Generate token with role and random string"""
    random_bytes = os.urandom(16)
    random_string = base64.b64encode(random_bytes).decode('utf-8')
    token = f"{userrole.value}:{random_string}"

    # Token and expiration stored together
    active_tokens[username] = (token, time.time() + TOKEN_EXP)
    return token

def verify_token(username, token):
    """Verify if token is still valid for user"""
    if username not in active_tokens:
        return False

    stored_token, expiry_time = active_tokens[username]
    if time.time() > expiry_time:
        # Token is already expired
        del active_tokens[username]
        return False
    return stored_token == token

def authenticate(username, pwd):
    """
    The authentication function accepting username and password
    """
    if username in users and users[username].password == pwd:
        # successful validation
        user = users[username]
        token = generate_token(username, user.role)
        return {"token": token, "role": user.role.value}

    # Authorization failed
    raise AuthorizationError("Authorization failed")