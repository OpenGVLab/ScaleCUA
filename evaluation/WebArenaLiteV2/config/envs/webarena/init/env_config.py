# websites domain
import json

WEBARENA_URL_JSON = "config/env/webarena/init/webarena_url.json"

with open(WEBARENA_URL_JSON, "r") as f:
    URL = json.load(f)

REDDIT = URL["REDDIT_URL"]
SHOPPING = URL["SHOPPING_URL"]
SHOPPING_ADMIN = URL["SHOPPING_ADMIN_URL"]
GITLAB = URL["GITLAB_URL"]
MAP = URL["MAP_URL"]

ACCOUNTS = {
    "reddit": {"username": "MarvelsGrantMan136", "password": "test1234"},
    "gitlab": {"username": "byteblaze", "password": "hello1234"},
    "shopping": {
        "username": "emma.lopez@gmail.com",
        "password": "Password.123",
    },
    "shopping_admin": {"username": "admin", "password": "admin1234"},
    "shopping_site_admin": {"username": "admin", "password": "admin1234"},
}

URL_MAPPINGS = {
    REDDIT: "http://reddit.com",
    SHOPPING: "http://onestopmarket.com",
    SHOPPING_ADMIN: "http://luma.com/admin",
    GITLAB: "http://gitlab.com",
    MAP: "http://openstreetmap.org",
}
