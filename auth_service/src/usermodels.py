from enum import Enum

class UserRole(Enum):
    ADMINISTRATOR = "administrator"
    AGENT = "agent"
    SECRETARY = "secretary"

class User:
    def __init__(self, username, password, role):
        self.username = username
        self.password = password
        self.role = role

users = {
    "mynames_admin": User("mynames_admin", "password123", UserRole.ADMINISTRATOR),
    "agent_007": User("agent_007", "Bond007", UserRole.AGENT),
    "stacy": User("stacy", "starbucks123", UserRole.SECRETARY)
}