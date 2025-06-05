from datetime import datetime, timedelta
from num2words import num2words

import json
import os


def format_amount_with_words(amount_str):
    """
    Преобразует сумму в строку вида:
    "123456.78 тенге (сто двадцать три тысячи четыреста пятьдесят шесть тенге 78 тиынов)"
    """
    if not amount_str:
        return None
    try:
        parts = amount_str.split('.')
        tenge = int(parts[0])
        tiyn = int(parts[1]) if len(parts) > 1 else 0

        tenge_words = num2words(tenge, lang='ru')
        if tiyn > 0:
            tiyn_words = num2words(tiyn, lang='ru')
            return f"{amount_str} тенге ({tenge_words} тенге {tiyn_words} тиынов)"
        else:
            return f"{amount_str} тенге ({tenge_words} тенге)"
    except:
        return f"{amount_str} тенге"


USERS_FILE = "allowed_users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)



def add_user(user_id, first_name="", last_name="", username="", days=0):
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({}, f)

    with open(USERS_FILE, "r") as f:
        users = json.load(f)

    access_until = None
    if days > 0:
        access_until = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    users[str(user_id)] = {
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "access_until": access_until
    }

    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def remove_user(user_id):
    users = get_user_list()
    users.pop(str(user_id), None)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def get_user_list():
    if not os.path.exists(USERS_FILE):
        return {}

    with open(USERS_FILE, "r") as f:
        return json.load(f)

def is_user_allowed(user_id):
    users = get_user_list()
    user = users.get(str(user_id))
    if not user:
        return False

    access_until = user.get("access_until")
    if access_until:
        try:
            return datetime.now().date() <= datetime.strptime(access_until, "%Y-%m-%d").date()
        except:
            return False
    return True

