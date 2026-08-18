# session.py — stores the logged-in user for the lifetime of the app
current_user = {
    "user_id": None,
    "name":    None,
    "role":    None,
    "token":   None,
}

def set_user(name: str, role: str, token: str):
    current_user["name"]  = name
    current_user["role"]  = role
    current_user["token"] = token

def clear():
    for k in current_user:
        current_user[k] = None
