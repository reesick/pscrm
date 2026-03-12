import requests
import os
from dotenv import load_dotenv

load_dotenv()

PROJECT_URL = os.getenv("SUPABASE_URL")
ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

users = [
    ("super_admin", "super_admin@pscrm.com", "Test@1234"),
    ("jssa",        "jssa@pscrm.com",        "Test@1234"),
    ("aa",          "aa@pscrm.com",           "Test@1234"),
    ("faa",         "faa@pscrm.com",          "Test@1234"),
]

for role, email, password in users:
    r = requests.post(
        f"{PROJECT_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password}
    )
    data = r.json()
    token = data.get("access_token", "ERROR: " + data.get("error_description", str(data)))
    print(f'{role}: "{token}"')
