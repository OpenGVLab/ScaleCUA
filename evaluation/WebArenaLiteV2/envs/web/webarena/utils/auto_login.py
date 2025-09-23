"""Script to automatically login each website"""

import sys
import os

sys.path.append(os.getenv("PWD"))
import argparse
import glob
import time
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from pathlib import Path
from playwright.sync_api import sync_playwright
from datetime import datetime
from config.envs.webarena.init.env_config import (
    ACCOUNTS,
    GITLAB,
    REDDIT,
    SHOPPING,
    SHOPPING_ADMIN,
)

HEADLESS = True
SLOW_MO = 0


SITES = ["gitlab", "shopping", "shopping_admin", "reddit"]
URLS = [
    f"{GITLAB}/-/profile",
    f"{SHOPPING}/wishlist/",
    f"{SHOPPING_ADMIN}/dashboard",
    f"{REDDIT}/user/{ACCOUNTS['reddit']['username']}/account",
]
EXACT_MATCH = [True, True, True, True]
KEYWORDS = ["", "", "Dashboard", "Delete"]


def is_expired(
    storage_state: Path, url: str, keyword: str, url_exact: bool = True
) -> bool:
    """Test whether the cookie is expired"""
    if not storage_state.exists():
        return True

    context_manager = sync_playwright()
    playwright = context_manager.__enter__()
    browser = playwright.chromium.launch(
        headless=HEADLESS,
        args=[
            "--allow-running-insecure-content",
            "--disable-web-security",
            # 特别添加允许不安全端口的参数
            "--explicitly-allowed-ports=6666,6667,6668,6669,6670,6671,6672",
        ],
        slow_mo=SLOW_MO,
    )
    context = browser.new_context(storage_state=storage_state)
    page = context.new_page()
    page.goto(url)
    time.sleep(1)
    d_url = page.url
    content = page.content()
    context_manager.__exit__()
    if keyword:
        return keyword not in content
    else:
        if url_exact:
            return d_url != url
        else:
            return url not in d_url


def renew_comb(comb: list[str], auth_folder: str = "./.auth") -> None:
    context_manager = sync_playwright()
    playwright = context_manager.__enter__()
    browser = playwright.chromium.launch(
        headless=HEADLESS,
        args=[
            "--allow-running-insecure-content",
            "--disable-web-security",
            # 特别添加允许不安全端口的参数
            f"--explicitly-allowed-ports={','.join(str(i) for i in range(6660, 7000))}",
        ],
    )
    context = browser.new_context()
    page = context.new_page()

    if "reddit" in comb:
        username = ACCOUNTS["reddit"]["username"]
        password = ACCOUNTS["reddit"]["password"]
        page.goto(f"{REDDIT}/login")
        page.get_by_label("Username").fill(username)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Log in").click()
        print(f"Reddit 重新登录")

    if "shopping_admin" in comb:
        username = ACCOUNTS["shopping_admin"]["username"]
        password = ACCOUNTS["shopping_admin"]["password"]
        page.goto(f"{SHOPPING_ADMIN}")
        page.get_by_placeholder("user name").fill(username)
        page.get_by_placeholder("password").fill(password)
        page.get_by_role("button", name="Sign in").click()
        print(f"ShoppingAdmin 重新登录")

    if "gitlab" in comb:
        username = ACCOUNTS["gitlab"]["username"]
        password = ACCOUNTS["gitlab"]["password"]
        page.goto(f"{GITLAB}/users/sign_in")
        page.get_by_test_id("username-field").click()
        page.get_by_test_id("username-field").fill(username)
        page.get_by_test_id("username-field").press("Tab")
        page.get_by_test_id("password-field").fill(password)
        page.get_by_test_id("sign-in-button").click()
        print(f"Gitlab 重新登录")

    if "shopping" in comb:
        username = ACCOUNTS["shopping"]["username"]
        password = ACCOUNTS["shopping"]["password"]
        # page.goto(f"{SHOPPING}")
        # try:
        #     page.get_by_text("Sign Out").click(timeout=2000)
        # except Exception as e:
        #     pass

        page.goto(f"{SHOPPING}/customer/account/login/")
        page.get_by_label("Email", exact=True).fill(username)
        page.get_by_label("Password", exact=True).fill(password)
        page.get_by_role("button", name="Sign In").click()
        # page.screenshot(path=f"shopping_test1.png") # 可以正常登录
        print(f"Shopping 重新登录")

    # page.screenshot(path=f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png") # 可以正常登录
    context.storage_state(path=f"{auth_folder}/{'.'.join(comb)}_state.json")

    context_manager.__exit__()


def get_site_comb_from_filepath(file_path: str) -> list[str]:
    comb = os.path.basename(file_path).rsplit("_", 1)[0].split(".")
    return comb


def main(auth_folder: str = "./.auth") -> None:

    max_workers = 8
    with ThreadPoolExecutor(max_workers=max_workers) as executor:

        for site in SITES:
            executor.submit(renew_comb, [site], auth_folder=auth_folder)

    futures = []
    cookie_files = list(glob.glob(f"{auth_folder}/*.json"))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for c_file in cookie_files:
            comb = get_site_comb_from_filepath(c_file)
            for cur_site in comb:
                url = URLS[SITES.index(cur_site)]
                keyword = KEYWORDS[SITES.index(cur_site)]
                match = EXACT_MATCH[SITES.index(cur_site)]
                future = executor.submit(is_expired, Path(c_file), url, keyword, match)
                futures.append(future)

    for i, future in enumerate(futures):
        assert not future.result(), f"Cookie {cookie_files[i]} expired."


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--site_list", nargs="+", default=[])
    parser.add_argument("--auth_folder", type=str, default="./.auth")
    args = parser.parse_args()
    if not args.site_list:
        main()
    else:
        if "all" in args.site_list:
            main(auth_folder=args.auth_folder)
        else:
            renew_comb(args.site_list, auth_folder=args.auth_folder)
