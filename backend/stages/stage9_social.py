"""
Stage 9 — Social & Username Intelligence
==========================================
Given a username (extracted from OCR, EXIF, or provided manually), searches
500+ social platforms, developer sites, gaming networks, and paste sites.

Inspired by Sherlock and Social Analyzer but built into the ImageTrace pipeline.
Also checks:
  - HaveIBeenPwned for breach exposure (if email provided)
  - GitHub for commits, repos, exposed secrets
  - Paste sites for mention leaks
  - Domain ownership (WHOIS)
"""

import os
import re
import json
import time
import socket
import hashlib
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

# ── Platform database ─────────────────────────────────────────────────────────
# Format: "Platform Name": ("url_template_{}", "check_method", "category")
# check_method: "status" (HTTP 200 = found), "content" (look for string in body)

PLATFORMS = {
    # Social media
    "Twitter/X":      ("https://x.com/{}",                       "status",  "social"),
    "Instagram":      ("https://www.instagram.com/{}/",           "status",  "social"),
    "TikTok":         ("https://www.tiktok.com/@{}",              "status",  "social"),
    "Facebook":       ("https://www.facebook.com/{}",             "status",  "social"),
    "Pinterest":      ("https://www.pinterest.com/{}/",           "status",  "social"),
    "Snapchat":       ("https://www.snapchat.com/add/{}",         "status",  "social"),
    "Tumblr":         ("https://{}.tumblr.com",                   "status",  "social"),
    "Reddit":         ("https://www.reddit.com/user/{}",          "status",  "social"),
    "LinkedIn":       ("https://www.linkedin.com/in/{}",          "status",  "social"),
    "VK":             ("https://vk.com/{}",                       "status",  "social"),
    "Mastodon":       ("https://mastodon.social/@{}",             "status",  "social"),
    "Threads":        ("https://www.threads.net/@{}",             "status",  "social"),
    "Bluesky":        ("https://bsky.app/profile/{}",             "status",  "social"),

    # Developer / tech
    "GitHub":         ("https://github.com/{}",                   "status",  "dev"),
    "GitLab":         ("https://gitlab.com/{}",                   "status",  "dev"),
    "Bitbucket":      ("https://bitbucket.org/{}",                "status",  "dev"),
    "HackerNews":     ("https://news.ycombinator.com/user?id={}", "status",  "dev"),
    "Stack Overflow": ("https://stackoverflow.com/users/{}",      "status",  "dev"),
    "Replit":         ("https://replit.com/@{}",                  "status",  "dev"),
    "Codepen":        ("https://codepen.io/{}",                   "status",  "dev"),
    "Dev.to":         ("https://dev.to/{}",                       "status",  "dev"),
    "Kaggle":         ("https://www.kaggle.com/{}",               "status",  "dev"),
    "HuggingFace":    ("https://huggingface.co/{}",               "status",  "dev"),
    "npm":            ("https://www.npmjs.com/~{}",               "status",  "dev"),
    "PyPI":           ("https://pypi.org/user/{}/",               "status",  "dev"),
    "DockerHub":      ("https://hub.docker.com/u/{}",             "status",  "dev"),

    # Gaming
    "Steam":          ("https://steamcommunity.com/id/{}",        "status",  "gaming"),
    "Twitch":         ("https://www.twitch.tv/{}",                "status",  "gaming"),
    "Xbox":           ("https://xboxgamertag.com/search/{}",      "status",  "gaming"),
    "PSN":            ("https://psnprofiles.com/{}",              "status",  "gaming"),
    "Roblox":         ("https://www.roblox.com/user.aspx?username={}", "status", "gaming"),
    "Minecraft":      ("https://api.mojang.com/users/profiles/minecraft/{}", "status", "gaming"),
    "Chess.com":      ("https://www.chess.com/member/{}",         "status",  "gaming"),
    "Lichess":        ("https://lichess.org/@/{}",                "status",  "gaming"),
    "Fortnite":       ("https://fortnitetracker.com/profile/all/{}", "status", "gaming"),
    "Speedrun.com":   ("https://www.speedrun.com/user/{}",        "status",  "gaming"),

    # Creative / content
    "YouTube":        ("https://www.youtube.com/@{}",             "status",  "creative"),
    "SoundCloud":     ("https://soundcloud.com/{}",               "status",  "creative"),
    "Spotify":        ("https://open.spotify.com/user/{}",        "status",  "creative"),
    "Bandcamp":       ("https://{}.bandcamp.com",                 "status",  "creative"),
    "Behance":        ("https://www.behance.net/{}",              "status",  "creative"),
    "Dribbble":       ("https://dribbble.com/{}",                 "status",  "creative"),
    "Deviantart":     ("https://www.deviantart.com/{}",           "status",  "creative"),
    "ArtStation":     ("https://www.artstation.com/{}",           "status",  "creative"),
    "Flickr":         ("https://www.flickr.com/people/{}",        "status",  "creative"),
    "500px":          ("https://500px.com/p/{}",                  "status",  "creative"),
    "Patreon":        ("https://www.patreon.com/{}",              "status",  "creative"),
    "OnlyFans":       ("https://onlyfans.com/{}",                 "status",  "creative"),
    "Substack":       ("https://{}.substack.com",                 "status",  "creative"),
    "Medium":         ("https://medium.com/@{}",                  "status",  "creative"),

    # Forums / communities
    "Quora":          ("https://www.quora.com/profile/{}",        "status",  "forum"),
    "Disqus":         ("https://disqus.com/by/{}/",               "status",  "forum"),
    "Gravatar":       ("https://en.gravatar.com/{}",              "status",  "forum"),
    "About.me":       ("https://about.me/{}",                     "status",  "forum"),
    "Linktree":       ("https://linktr.ee/{}",                    "status",  "forum"),
    "Keybase":        ("https://keybase.io/{}",                   "status",  "forum"),
    "Telegram":       ("https://t.me/{}",                         "status",  "forum"),
    "Signal":         ("https://signal.me/#p/{}",                 "status",  "forum"),
    "Wire":           ("https://app.wire.com/{}",                 "status",  "forum"),
    "Discord (lookup)": ("https://discord.id/?prefill={}",        "status",  "forum"),

    # Shopping / finance
    "Etsy":           ("https://www.etsy.com/shop/{}",            "status",  "commerce"),
    "eBay":           ("https://www.ebay.com/usr/{}",             "status",  "commerce"),
    "Fiverr":         ("https://www.fiverr.com/{}",               "status",  "commerce"),
    "Upwork":         ("https://www.upwork.com/freelancers/~{}",  "status",  "commerce"),
    "PayPal":         ("https://www.paypal.me/{}",                "status",  "commerce"),
    "Venmo":          ("https://account.venmo.com/u/{}",          "status",  "commerce"),
    "CashApp":        ("https://cash.app/${}",                    "status",  "commerce"),

    # Crypto / web3
    "OpenSea":        ("https://opensea.io/{}",                   "status",  "crypto"),
    "Etherscan":      ("https://etherscan.io/address/{}",         "status",  "crypto"),

    # Professional
    "Crunchbase":     ("https://www.crunchbase.com/person/{}",    "status",  "professional"),
    "AngelList":      ("https://angel.co/u/{}",                   "status",  "professional"),
    "ProductHunt":    ("https://www.producthunt.com/@{}",         "status",  "professional"),
    "ResearchGate":   ("https://www.researchgate.net/profile/{}","status",  "professional"),
    "Academia.edu":   ("https://independent.academia.edu/{}",     "status",  "professional"),

    # Paste sites (breach/leak hunting)
    "Pastebin":       ("https://pastebin.com/u/{}",               "status",  "paste"),
    "Ghostbin":       ("https://ghostbin.com/user/{}",            "status",  "paste"),
    "Rentry":         ("https://rentry.co/{}",                    "status",  "paste"),

    # Dating
    "Tinder":         ("https://www.tinder.com/@{}",              "status",  "dating"),
    "OKCupid":        ("https://www.okcupid.com/profile/{}",      "status",  "dating"),
    "Badoo":          ("https://badoo.com/en/{}",                 "status",  "dating"),
    "Bumble":         ("https://bumble.com/en/{}",                "status",  "dating"),
    "Hinge":          ("https://hinge.co/{}",                     "status",  "dating"),
    "PlentyOfFish":   ("https://www.pof.com/viewprofile.aspx?profile_id={}", "status", "dating"),
    "Zoosk":          ("https://www.zoosk.com/{}",                "status",  "dating"),
    "MeetMe":         ("https://www.meetme.com/apps/profile/{}",  "status",  "dating"),

    # Fitness / location-revealing
    "Strava":         ("https://www.strava.com/athletes/{}",      "status",  "fitness"),
    "AllTrails":      ("https://www.alltrails.com/members/{}",    "status",  "fitness"),
    "Garmin Connect": ("https://connect.garmin.com/modern/profile/{}", "status", "fitness"),
    "Nike Run Club":  ("https://www.nike.com/member/profile/{}",  "status",  "fitness"),
    "Peloton":        ("https://members.onepeloton.com/members/{}/overview", "status", "fitness"),
    "MapMyRun":       ("https://www.mapmyrun.com/profile/{}/",    "status",  "fitness"),
    "Runkeeper":      ("https://runkeeper.com/user/{}/profile",   "status",  "fitness"),

    # Books / media (identity correlation)
    "Goodreads":      ("https://www.goodreads.com/{}",            "status",  "media"),
    "Letterboxd":     ("https://letterboxd.com/{}",               "status",  "media"),
    "Trakt.tv":       ("https://trakt.tv/users/{}",               "status",  "media"),
    "Last.fm":        ("https://www.last.fm/user/{}",             "status",  "media"),
    "MyAnimeList":    ("https://myanimelist.net/profile/{}",      "status",  "media"),
    "AniList":        ("https://anilist.co/user/{}",              "status",  "media"),

    # Alternative social
    "BeReal":         ("https://bere.al/{}",                      "status",  "social"),
    "Lemon8":         ("https://www.lemon8-app.com/@{}",          "status",  "social"),
    "Clubhouse":      ("https://www.clubhouse.com/@{}",           "status",  "social"),
    "Vero":           ("https://vero.co/{}",                      "status",  "social"),
    "Minds":          ("https://www.minds.com/{}",                "status",  "social"),
    "MeWe":           ("https://mewe.com/i/{}",                   "status",  "social"),
    "Parler":         ("https://parler.com/{}",                   "status",  "social"),
    "Gab":            ("https://gab.com/{}",                      "status",  "social"),
    "Truth Social":   ("https://truthsocial.com/@{}",             "status",  "social"),
    "Rumble":         ("https://rumble.com/user/{}",              "status",  "social"),
    "Mewe2":          ("https://mewe.com/profile/{}",             "status",  "social"),
    "Ello":           ("https://ello.co/{}",                      "status",  "social"),
    "Mix":            ("https://mix.com/{}",                      "status",  "social"),
    "Plurk":          ("https://www.plurk.com/{}",                "status",  "social"),
    "Amino":          ("https://aminoapps.com/u/{}",              "status",  "social"),

    # Professional / freelance
    "Xing":           ("https://www.xing.com/profile/{}",         "status",  "professional"),
    "Freelancer":     ("https://www.freelancer.com/u/{}",         "status",  "professional"),
    "Guru":           ("https://www.guru.com/freelancers/{}",     "status",  "professional"),
    "PeoplePerHour":  ("https://www.peopleperhour.com/freelancer/{}", "status", "professional"),
    "Toptal":         ("https://www.toptal.com/resume/{}",        "status",  "professional"),
    "Clarity.fm":     ("https://clarity.fm/{}",                   "status",  "professional"),
    "Coroflot":       ("https://www.coroflot.com/{}",             "status",  "professional"),

    # Dev communities
    "Lobste.rs":      ("https://lobste.rs/u/{}",                  "status",  "dev"),
    "Sourcehut":      ("https://sr.ht/~{}",                       "status",  "dev"),
    "Codesandbox":    ("https://codesandbox.io/u/{}",             "status",  "dev"),
    "Hashnode":       ("https://hashnode.com/@{}",                "status",  "dev"),
    "Hackaday":       ("https://hackaday.io/{}",                  "status",  "dev"),
    "Glitch":         ("https://glitch.com/@{}",                  "status",  "dev"),
    "Observable":     ("https://observablehq.com/@{}",            "status",  "dev"),
    "Exercism":       ("https://exercism.io/profiles/{}",         "status",  "dev"),
    "LeetCode":       ("https://leetcode.com/{}",                 "status",  "dev"),
    "HackerEarth":    ("https://www.hackerearth.com/@{}",         "status",  "dev"),
    "Codeforces":     ("https://codeforces.com/profile/{}",       "status",  "dev"),
    "AtCoder":        ("https://atcoder.jp/users/{}",             "status",  "dev"),
    "CodinGame":      ("https://www.codingame.com/profile/{}",    "status",  "dev"),
    "Peerlist":       ("https://peerlist.io/{}",                  "status",  "dev"),

    # Crypto / web3
    "Rarible":        ("https://rarible.com/{}",                  "status",  "crypto"),
    "Foundation":     ("https://foundation.app/@{}",              "status",  "crypto"),
    "Mirror.xyz":     ("https://mirror.xyz/{}",                   "status",  "crypto"),
    "LooksRare":      ("https://looksrare.org/accounts/{}",       "status",  "crypto"),
    "CryptoKitties":  ("https://www.cryptokitties.co/profile/{}","status",  "crypto"),
    "Nifty Gateway":  ("https://niftygateway.com/{}",             "status",  "crypto"),

    # Regional (high OSINT value)
    "Weibo":          ("https://weibo.com/{}",                    "status",  "social"),
    "Naver Blog":     ("https://blog.naver.com/{}",               "status",  "social"),
    "Bilibili":       ("https://space.bilibili.com/{}",           "status",  "social"),
    "OK.ru":          ("https://ok.ru/profile/{}",                "status",  "social"),
    "Mail.ru":        ("https://my.mail.ru/mail/{}",              "status",  "social"),
    "Odnoklassniki":  ("https://ok.ru/{}",                        "status",  "social"),
    "Ask.fm":         ("https://ask.fm/{}",                       "status",  "social"),
    "LiveJournal":    ("https://{}.livejournal.com",              "status",  "social"),
    "Diary.ru":       ("https://www.diary.ru/~{}",                "status",  "social"),
    "Fotki.yandex":   ("https://fotki.yandex.ru/users/{}",        "status",  "social"),
    "Xanga":          ("https://xanga.com/{}",                    "status",  "social"),

    # Photography
    "Unsplash":       ("https://unsplash.com/@{}",                "status",  "creative"),
    "EyeEm":          ("https://www.eyeem.com/u/{}",              "status",  "creative"),
    "Pixabay":        ("https://pixabay.com/users/{}/",           "status",  "creative"),
    "Pexels":         ("https://www.pexels.com/@{}",              "status",  "creative"),
    "Smugmug":        ("https://{}.smugmug.com",                  "status",  "creative"),
    "ImageShack":     ("https://imageshack.com/user/{}",          "status",  "creative"),
    "Imgur":          ("https://imgur.com/user/{}",               "status",  "creative"),
    "Wattpad":        ("https://www.wattpad.com/user/{}",         "status",  "creative"),
    "Fanfiction":     ("https://www.fanfiction.net/u/{}",         "status",  "creative"),
    "Archive of Our Own": ("https://archiveofourown.org/users/{}","status",  "creative"),

    # News / politics
    "Disclose.tv":    ("https://disclose.tv/user/{}",             "status",  "forum"),
    "Locals":         ("https://{}.locals.com",                   "status",  "forum"),
    "Substack2":      ("https://substack.com/@{}",                "status",  "forum"),
    "Ghost":          ("https://{}.ghost.io",                     "status",  "forum"),
    "Wordpress":      ("https://{}.wordpress.com",                "status",  "forum"),
    "Blogger":        ("https://{}.blogspot.com",                 "status",  "forum"),
    "Weebly":         ("https://{}.weebly.com",                   "status",  "forum"),
    "Wix":            ("https://{}.wixsite.com",                  "status",  "forum"),
    "Squarespace":    ("https://{}.squarespace.com",              "status",  "forum"),

    # More paste/leak
    "Hastebin":       ("https://hastebin.com/{}",                 "status",  "paste"),
    "Privatebin":     ("https://privatebin.net/{}",               "status",  "paste"),

    # Gaming extras
    "Battle.net":     ("https://battle.net/{}",                   "status",  "gaming"),
    "Origin":         ("https://www.origin.com/usa/en-us/profile/user/{}", "status", "gaming"),
    "Epic Games":     ("https://www.epicgames.com/id/{}",         "status",  "gaming"),
    "GOG":            ("https://www.gog.com/u/{}",                "status",  "gaming"),
    "Itch.io":        ("https://{}.itch.io",                      "status",  "gaming"),
    "GameBattles":    ("https://gamebattles.majorleaguegaming.com/pc/user/{}", "status", "gaming"),
    "Faceit":         ("https://www.faceit.com/en/players/{}",    "status",  "gaming"),
    "ESEA":           ("https://play.esea.net/users/{}",          "status",  "gaming"),
    "Overwolf":       ("https://www.overwolf.com/user/{}",        "status",  "gaming"),
    "Wargaming":      ("https://worldoftanks.com/en/community/accounts/{}/", "status", "gaming"),

    # Music extras
    "ReverbNation":   ("https://www.reverbnation.com/{}",         "status",  "creative"),
    "Audiomack":      ("https://audiomack.com/{}",                "status",  "creative"),
    "Mixcloud":       ("https://www.mixcloud.com/{}/",            "status",  "creative"),
    "Audiojungle":    ("https://audiojungle.net/user/{}/portfolio","status", "creative"),
    "Beatport":       ("https://www.beatport.com/artist/{}/1",    "status",  "creative"),

    # Science / academia
    "ORCID":          ("https://orcid.org/{}",                    "status",  "professional"),
    "Google Scholar": ("https://scholar.google.com/citations?user={}", "status", "professional"),
    "Mendeley":       ("https://www.mendeley.com/profiles/{}",    "status",  "professional"),
    "Zenodo":         ("https://zenodo.org/search?q={}",          "status",  "professional"),
    "SSRN":           ("https://papers.ssrn.com/sol3/cf_dev/AbsByAuth.cfm?per_id={}", "status", "professional"),

    # Commerce extras
    "Amazon":         ("https://www.amazon.com/gp/profile/amzn1.account.{}","status","commerce"),
    "Poshmark":       ("https://poshmark.com/closet/{}",          "status",  "commerce"),
    "Depop":          ("https://www.depop.com/{}",                "status",  "commerce"),
    "Vinted":         ("https://www.vinted.com/member/{}",        "status",  "commerce"),
    "Mercari":        ("https://www.mercari.com/u/{}",            "status",  "commerce"),
    "Redbubble":      ("https://www.redbubble.com/people/{}",     "status",  "commerce"),
    "Zazzle":         ("https://www.zazzle.com/{}",               "status",  "commerce"),
    "Society6":       ("https://society6.com/{}",                 "status",  "commerce"),
    "TeePublic":      ("https://www.teepublic.com/user/{}",       "status",  "commerce"),
    "Threadless":     ("https://www.threadless.com/@{}",          "status",  "commerce"),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Single platform check ─────────────────────────────────────────────────────

def _check_platform(name: str, url_tpl: str, username: str,
                    method: str, category: str, timeout: int = 8) -> dict:
    url = url_tpl.format(quote(username))
    result = {
        "platform": name,
        "url": url,
        "category": category,
        "found": False,
        "status_code": None,
        "error": None,
    }
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout,
                            allow_redirects=True)
        result["status_code"] = resp.status_code

        if method == "status":
            # 200 = found, anything else = not found or private
            result["found"] = resp.status_code == 200
        elif method == "content":
            result["found"] = resp.status_code == 200

        # Extra: detect "not found" pages that return 200
        not_found_strings = [
            "page not found", "user not found", "account not found",
            "does not exist", "no user", "404", "this account doesn't exist",
            "sorry, that page doesn't exist",
        ]
        if result["found"] and method == "status":
            body_lower = resp.text[:2000].lower()
            if any(s in body_lower for s in not_found_strings):
                result["found"] = False
                result["false_positive"] = True

    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.ConnectionError:
        result["error"] = "connection_error"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── GitHub deep search ────────────────────────────────────────────────────────

def _github_deep(username: str, token: str = "") -> dict:
    """
    Deep GitHub intelligence: repos, commit emails, gists, org memberships.
    Uses GitHub API (higher rate limits with token).
    """
    result = {
        "exists": False,
        "profile": {},
        "repos": [],
        "emails_found": [],
        "orgs": [],
        "gists": [],
        "error": None,
    }
    headers = {"User-Agent": "ImageTrace-OSINT"}
    if token:
        headers["Authorization"] = f"token {token}"

    base = "https://api.github.com"
    try:
        # User profile
        r = requests.get(f"{base}/users/{username}", headers=headers, timeout=10)
        if r.status_code == 404:
            return result
        if r.status_code != 200:
            result["error"] = f"HTTP {r.status_code}"
            return result

        data = r.json()
        result["exists"] = True
        result["profile"] = {
            "name":       data.get("name"),
            "bio":        data.get("bio"),
            "company":    data.get("company"),
            "location":   data.get("location"),
            "email":      data.get("email"),
            "blog":       data.get("blog"),
            "twitter":    data.get("twitter_username"),
            "followers":  data.get("followers"),
            "following":  data.get("following"),
            "public_repos": data.get("public_repos"),
            "created_at": data.get("created_at"),
            "avatar_url": data.get("avatar_url"),
        }
        if data.get("email"):
            result["emails_found"].append(data["email"])

        # Repos (top 10 by stars)
        repos_r = requests.get(
            f"{base}/users/{username}/repos?sort=stars&per_page=10",
            headers=headers, timeout=10
        )
        if repos_r.status_code == 200:
            for repo in repos_r.json():
                result["repos"].append({
                    "name":        repo.get("full_name"),
                    "description": repo.get("description"),
                    "stars":       repo.get("stargazers_count"),
                    "language":    repo.get("language"),
                    "url":         repo.get("html_url"),
                    "updated":     repo.get("updated_at"),
                })

        # Orgs
        orgs_r = requests.get(f"{base}/users/{username}/orgs", headers=headers, timeout=10)
        if orgs_r.status_code == 200:
            result["orgs"] = [o.get("login") for o in orgs_r.json()]

        # Gists
        gists_r = requests.get(
            f"{base}/users/{username}/gists?per_page=5",
            headers=headers, timeout=10
        )
        if gists_r.status_code == 200:
            for g in gists_r.json():
                result["gists"].append({
                    "description": g.get("description"),
                    "url":         g.get("html_url"),
                    "created":     g.get("created_at"),
                    "files":       list(g.get("files", {}).keys()),
                })

        # Try to extract emails from recent commits
        events_r = requests.get(
            f"{base}/users/{username}/events/public?per_page=10",
            headers=headers, timeout=10
        )
        if events_r.status_code == 200:
            for event in events_r.json():
                commits = event.get("payload", {}).get("commits", [])
                for commit in commits:
                    email = commit.get("author", {}).get("email", "")
                    if email and "@" in email and "noreply" not in email:
                        if email not in result["emails_found"]:
                            result["emails_found"].append(email)

    except Exception as e:
        result["error"] = str(e)

    return result


# ── HaveIBeenPwned ────────────────────────────────────────────────────────────

def _hibp_check(email: str, api_key: str = "") -> dict:
    """Check HaveIBeenPwned for breach exposure. Free tier = no key but rate-limited."""
    result = {"breaches": [], "paste_count": 0, "error": None}
    if not email or "@" not in email:
        return result

    headers = {"User-Agent": "ImageTrace-OSINT", "hibp-api-key": api_key}
    try:
        time.sleep(1.5)  # HIBP rate limit
        r = requests.get(
            f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}",
            headers=headers, timeout=15
        )
        if r.status_code == 200:
            for breach in r.json():
                result["breaches"].append({
                    "name":         breach.get("Name"),
                    "domain":       breach.get("Domain"),
                    "date":         breach.get("BreachDate"),
                    "pwn_count":    breach.get("PwnCount"),
                    "data_classes": breach.get("DataClasses", []),
                    "verified":     breach.get("IsVerified"),
                })
        elif r.status_code == 404:
            pass  # Not found = clean
        elif r.status_code == 401:
            result["error"] = "HIBP API key required for this check"
        else:
            result["error"] = f"HTTP {r.status_code}"
    except Exception as e:
        result["error"] = str(e)

    return result


# ── Paste site scan ───────────────────────────────────────────────────────────

def _paste_scan(username: str) -> dict:
    """Search publicly indexed paste sites for username mentions."""
    result = {"mentions": [], "error": None}
    # Use Google dork via SerpAPI or directly request paste site search pages
    paste_sites = [
        f"https://pastebin.com/search?q={quote(username)}",
        f"https://ghostbin.com/search?q={quote(username)}",
    ]
    for url in paste_sites:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200 and username.lower() in r.text.lower():
                result["mentions"].append({"site": url, "found": True})
        except Exception:
            pass
    return result


# ── Domain / WHOIS check ──────────────────────────────────────────────────────

def _domain_check(username: str) -> dict:
    """Check if username.com / username.io / username.dev are registered."""
    result = {"domains": []}
    tlds = [".com", ".net", ".io", ".dev", ".me", ".co", ".org"]
    for tld in tlds:
        domain = f"{username}{tld}"
        try:
            socket.gethostbyname(domain)
            result["domains"].append({"domain": domain, "registered": True})
        except socket.gaierror:
            result["domains"].append({"domain": domain, "registered": False})
        except Exception:
            pass
    return result


# ── Gravatar lookup ───────────────────────────────────────────────────────────

def _gravatar_lookup(email: str) -> dict:
    """MD5(email) → Gravatar avatar + JSON profile. 200 = account exists."""
    result = {
        "has_gravatar": False,
        "avatar_url": None,
        "md5_hash": None,
        "profile": {},
        "error": None,
    }
    if not email or "@" not in email:
        result["error"] = "No email provided"
        return result

    email_hash = hashlib.md5(email.lower().strip().encode()).hexdigest()
    result["md5_hash"] = email_hash
    result["avatar_url"] = f"https://www.gravatar.com/avatar/{email_hash}?d=404&s=200"

    try:
        # Check if avatar exists (d=404 returns 404 if no account)
        r = requests.get(result["avatar_url"], headers=HEADERS, timeout=8)
        if r.status_code == 200:
            result["has_gravatar"] = True
            # Try to fetch full profile JSON
            profile_url = f"https://www.gravatar.com/{email_hash}.json"
            try:
                pr = requests.get(profile_url, headers=HEADERS, timeout=8)
                if pr.status_code == 200:
                    data = pr.json().get("entry", [{}])[0]
                    result["profile"] = {
                        "display_name":  data.get("displayName"),
                        "preferred_name": data.get("name", {}).get("formatted"),
                        "about":         data.get("aboutMe"),
                        "location":      data.get("currentLocation"),
                        "job_title":     data.get("currentEmployer") or (data.get("accounts") or [{}])[0].get("jobTitle"),
                        "accounts":      [
                            {"domain": a.get("domain"), "url": a.get("url")}
                            for a in data.get("accounts", [])
                        ],
                        "verified_accounts": [
                            a.get("domain") for a in data.get("accounts", [])
                            if a.get("verified")
                        ],
                        "urls":          [u.get("value") for u in data.get("urls", [])],
                        "profile_url":   f"https://gravatar.com/profiles/{email_hash}",
                    }
            except Exception:
                pass  # Profile might be private even if avatar exists
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Email permutation generator ───────────────────────────────────────────────

def _generate_email_permutations(name: str, domains: list | None = None) -> list[str]:
    """
    Generate likely email addresses from a full name.
    e.g. "John Smith" → john.smith@gmail.com, jsmith@gmail.com, etc.
    """
    if not name or not name.strip():
        return []

    if domains is None:
        domains = [
            "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
            "protonmail.com", "icloud.com", "live.com",
        ]

    # Parse name into parts
    parts = name.lower().strip().split()
    if len(parts) == 0:
        return []
    first = parts[0]
    last  = parts[-1] if len(parts) > 1 else ""
    fi    = first[0] if first else ""
    li    = last[0]  if last  else ""

    # Build patterns
    patterns = []
    if last:
        patterns = [
            f"{first}.{last}",        # john.smith
            f"{first}{last}",         # johnsmith
            f"{first}_{last}",        # john_smith
            f"{fi}{last}",            # jsmith
            f"{first}.{li}",          # john.s
            f"{fi}.{last}",           # j.smith
            f"{last}.{first}",        # smith.john
            f"{last}{fi}",            # smithj
            f"{last}_{first}",        # smith_john
            f"{first}",               # john
            f"{last}",                # smith
            f"{first}{li}",           # johns
            f"{fi}{li}",              # js
        ]
    else:
        patterns = [first, f"{first}1", f"{first}2", f"{first}123"]

    # Cross with domains — limit to top 5 domains × all patterns
    emails = []
    for domain in domains[:5]:
        for pattern in patterns:
            if pattern:
                emails.append(f"{pattern}@{domain}")

    # Deduplicate preserving order
    seen = set()
    unique = []
    for e in emails:
        if e not in seen:
            seen.add(e)
            unique.append(e)

    return unique[:50]  # cap at 50


# ── Phone number intelligence ─────────────────────────────────────────────────

def _phone_intel(phone_number: str) -> dict:
    """
    Parse + classify a phone number: country, region, type, formats.
    Uses phonenumbers library (offline, pure Python).
    """
    result = {
        "valid": False,
        "country": None,
        "country_code": None,
        "region": None,
        "number_type": None,
        "international_format": None,
        "national_format": None,
        "e164_format": None,
        "carrier": None,
        "error": None,
    }

    if not phone_number:
        result["error"] = "No phone number provided"
        return result

    try:
        import phonenumbers
        from phonenumbers import geocoder, carrier, number_type, PhoneNumberType

        # Try parsing — if no country code given, default US
        try:
            pn = phonenumbers.parse(phone_number, None)
        except phonenumbers.phonenumberutil.NumberParseException:
            pn = phonenumbers.parse(phone_number, "US")

        result["valid"] = phonenumbers.is_valid_number(pn)
        if not result["valid"]:
            result["error"] = "Invalid phone number"
            return result

        result["country_code"]         = pn.country_code
        result["international_format"] = phonenumbers.format_number(
            pn, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        result["national_format"]      = phonenumbers.format_number(
            pn, phonenumbers.PhoneNumberFormat.NATIONAL)
        result["e164_format"]          = phonenumbers.format_number(
            pn, phonenumbers.PhoneNumberFormat.E164)

        region = phonenumbers.region_code_for_number(pn)
        result["region"]  = region
        result["country"] = geocoder.description_for_number(pn, "en")

        # Number type
        nt = phonenumbers.number_type(pn)
        type_map = {
            PhoneNumberType.MOBILE:            "Mobile",
            PhoneNumberType.FIXED_LINE:        "Fixed Line",
            PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed/Mobile",
            PhoneNumberType.TOLL_FREE:         "Toll-Free",
            PhoneNumberType.PREMIUM_RATE:      "Premium Rate",
            PhoneNumberType.VOIP:              "VoIP",
            PhoneNumberType.PERSONAL_NUMBER:   "Personal",
            PhoneNumberType.PAGER:             "Pager",
            PhoneNumberType.UAN:               "UAN",
            PhoneNumberType.UNKNOWN:           "Unknown",
        }
        result["number_type"] = type_map.get(nt, "Unknown")

        # Carrier (works for mobile numbers)
        try:
            c = carrier.name_for_number(pn, "en")
            result["carrier"] = c if c else None
        except Exception:
            pass

    except ImportError:
        result["error"] = "phonenumbers library not installed"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── maigret (3000+ sites) ─────────────────────────────────────────────────────

def _maigret_search(username: str) -> dict:
    """
    Run maigret via subprocess (pip install maigret).
    Returns found sites, linked usernames, linked emails.
    Graceful fallback if not installed.
    """
    result = {
        "available": False,
        "sites_found": [],
        "linked_usernames": [],
        "linked_emails": [],
        "raw_count": 0,
        "error": None,
    }
    if not username:
        return result

    import subprocess
    import shutil

    if not shutil.which("maigret"):
        result["error"] = "maigret not installed (pip install maigret)"
        return result

    result["available"] = True
    try:
        proc = subprocess.run(
            ["maigret", username, "--json", "-",
             "--retries", "1", "--timeout", "5",
             "--no-progressbar", "--ignore-cert-errors"],
            capture_output=True, text=True, timeout=120
        )
        if proc.returncode not in (0, 1):
            result["error"] = f"maigret exit {proc.returncode}: {proc.stderr[:200]}"
            return result

        # Parse JSONL or JSON output
        import json as _json
        lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
        for line in lines:
            try:
                entry = _json.loads(line)
                # maigret JSON format: {site_name: {status, url, ...}}
                if isinstance(entry, dict):
                    for site, data in entry.items():
                        if isinstance(data, dict) and data.get("status") == "Claimed":
                            result["sites_found"].append({
                                "platform": site,
                                "url":      data.get("url", ""),
                                "category": data.get("tags", [""])[0] if data.get("tags") else "",
                            })
                            # Linked identity info
                            for key in ("linked_username", "username"):
                                if data.get(key) and data[key] != username:
                                    if data[key] not in result["linked_usernames"]:
                                        result["linked_usernames"].append(data[key])
                            if data.get("email"):
                                if data["email"] not in result["linked_emails"]:
                                    result["linked_emails"].append(data["email"])
            except _json.JSONDecodeError:
                pass

        result["raw_count"] = len(result["sites_found"])
    except subprocess.TimeoutExpired:
        result["error"] = "maigret timed out (>120s)"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── holehe (email → 120 sites) ────────────────────────────────────────────────

def _holehe_check(email: str) -> dict:
    """
    Run holehe via subprocess (pip install holehe).
    Checks if email is registered on ~120 sites.
    """
    result = {
        "available": False,
        "sites_found": [],
        "sites_not_found": [],
        "sites_count": 0,
        "error": None,
    }
    if not email or "@" not in email:
        result["error"] = "No valid email"
        return result

    import subprocess
    import shutil

    if not shutil.which("holehe"):
        result["error"] = "holehe not installed (pip install holehe)"
        return result

    result["available"] = True
    try:
        proc = subprocess.run(
            ["holehe", "--only-used", "--no-color", email],
            capture_output=True, text=True, timeout=120
        )
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.startswith("[+]"):
                site = line[3:].strip().split(" ")[0]
                result["sites_found"].append(site)
            elif line.startswith("[-]"):
                site = line[3:].strip().split(" ")[0]
                result["sites_not_found"].append(site)
        result["sites_count"] = len(result["sites_found"])
    except subprocess.TimeoutExpired:
        result["error"] = "holehe timed out"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── phoneinfoga ───────────────────────────────────────────────────────────────

def _phoneinfoga_scan(phone: str) -> dict:
    """
    Run phoneinfoga via subprocess (pip install phoneinfoga or binary in PATH).
    Returns carrier, line type, spam score, formats.
    Complements phonenumbers offline parsing with live lookups.
    """
    result = {
        "available": False,
        "carrier": None,
        "line_type": None,
        "valid": None,
        "formats": {},
        "spam_score": None,
        "raw_output": "",
        "error": None,
    }
    if not phone:
        return result

    import subprocess
    import shutil

    if not shutil.which("phoneinfoga"):
        result["error"] = "phoneinfoga not installed"
        return result

    result["available"] = True
    try:
        proc = subprocess.run(
            ["phoneinfoga", "scan", "-n", phone],
            capture_output=True, text=True, timeout=30
        )
        result["raw_output"] = proc.stdout[:2000]
        # Parse key-value lines
        for line in proc.stdout.splitlines():
            line = line.strip()
            if ":" in line:
                key, _, val = line.partition(":")
                key = key.strip().lower().replace(" ", "_")
                val = val.strip()
                if "carrier" in key:
                    result["carrier"] = val
                elif "line_type" in key or "number_type" in key:
                    result["line_type"] = val
                elif "valid" in key:
                    result["valid"] = val.lower() in ("true", "yes", "1")
                elif "spam" in key:
                    try:
                        result["spam_score"] = float(val.replace("%", ""))
                    except ValueError:
                        pass
    except subprocess.TimeoutExpired:
        result["error"] = "phoneinfoga timed out"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ── Main search function ──────────────────────────────────────────────────────

def search(
    username: str,
    email: str = "",
    github_token: str = "",
    hibp_key: str = "",
    phone: str = "",
    name: str = "",
    max_workers: int = 30,
    categories: list[str] | None = None,
    timeout: int = 8,
    run_maigret: bool = True,
    run_holehe: bool = True,
) -> dict:
    """
    Search 280+ platforms + maigret 3000+ for username; compile intelligence dossier.

    Parameters
    ----------
    username     : target username to search
    email        : optional email for HIBP, Gravatar, holehe checks
    github_token : optional GitHub token for higher API rate limits
    hibp_key     : optional HaveIBeenPwned API key
    phone        : optional phone number for phone intel + phoneinfoga
    name         : optional full name (First Last) for email permutation generation
    max_workers  : concurrent HTTP requests (default 30)
    categories   : list of categories to check, None = all
    timeout      : per-request timeout seconds
    run_maigret  : run maigret if installed (may take 60-120s)
    run_holehe   : run holehe if installed and email provided
    """
    username = username.strip().lstrip("@")
    if not username:
        return {"error": "No username provided"}

    github_token = github_token or os.environ.get("GITHUB_TOKEN", "")
    hibp_key     = hibp_key     or os.environ.get("HIBP_API_KEY", "")

    # Filter platforms by category
    platforms_to_check = {
        name: (url, method, cat)
        for name, (url, method, cat) in PLATFORMS.items()
        if categories is None or cat in categories
    }

    print(f"[Stage 9] Searching {len(platforms_to_check)} platforms for '{username}'...")

    # Parallel platform checks
    platform_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _check_platform, name, url, username, method, cat, timeout
            ): name
            for name, (url, method, cat) in platforms_to_check.items()
        }
        for future in as_completed(futures):
            try:
                platform_results.append(future.result())
            except Exception:
                pass

    # Sort: found first, then alphabetical
    platform_results.sort(key=lambda x: (not x["found"], x["platform"]))

    found = [r for r in platform_results if r["found"]]
    not_found = [r for r in platform_results if not r["found"] and not r.get("error")]
    errors = [r for r in platform_results if r.get("error")]

    # Category breakdown
    by_category: dict[str, list] = {}
    for r in found:
        cat = r["category"]
        by_category.setdefault(cat, []).append(r)

    # GitHub deep intel
    print(f"[Stage 9] Running GitHub deep analysis...")
    github = _github_deep(username, github_token)

    # Add any emails from GitHub to the email list
    emails_to_check = set()
    if email:
        emails_to_check.add(email)
    emails_to_check.update(github.get("emails_found", []))

    # HIBP breach check
    hibp_results = {}
    for em in emails_to_check:
        print(f"[Stage 9] Checking breach database for {em}...")
        hibp_results[em] = _hibp_check(em, hibp_key)

    # Paste site scan
    print(f"[Stage 9] Scanning paste sites...")
    pastes = _paste_scan(username)

    # Domain check
    print(f"[Stage 9] Checking domains...")
    domains = _domain_check(username)
    registered_domains = [d for d in domains["domains"] if d["registered"]]

    # Gravatar lookup
    gravatar = {}
    if email:
        print(f"[Stage 9] Gravatar lookup for {email}...")
        gravatar = _gravatar_lookup(email)

    # Email permutations from name
    email_permutations = []
    if name:
        print(f"[Stage 9] Generating email permutations for '{name}'...")
        email_permutations = _generate_email_permutations(name)

    # Phone intelligence
    phone_intel = {}
    phoneinfoga = {}
    if phone:
        print(f"[Stage 9] Analyzing phone number {phone}...")
        phone_intel = _phone_intel(phone)
        phoneinfoga = _phoneinfoga_scan(phone)

    # maigret — 3000+ sites (optional, slower)
    maigret = {}
    if run_maigret:
        print(f"[Stage 9] Running maigret (3000+ sites)...")
        maigret = _maigret_search(username)
        # Merge maigret found sites into found list (avoid duplicates by URL)
        existing_urls = {r["url"] for r in found}
        for site in maigret.get("sites_found", []):
            if site.get("url") and site["url"] not in existing_urls:
                found.append({
                    "platform": site["platform"],
                    "url":      site["url"],
                    "category": site.get("category", "social"),
                    "found":    True,
                    "status_code": 200,
                    "error":    None,
                    "source":   "maigret",
                })
                existing_urls.add(site["url"])
                # Re-add to by_category
                cat = site.get("category", "social")
                by_category.setdefault(cat, []).append(found[-1])
        # Add any new linked emails/usernames to emails_to_check
        for linked_email in maigret.get("linked_emails", []):
            emails_to_check.add(linked_email)

    # holehe — email registered on 120 sites
    holehe = {}
    if run_holehe and email:
        print(f"[Stage 9] Running holehe for {email}...")
        holehe = _holehe_check(email)

    # Risk score
    risk = 0
    risk += len(found) * 2
    risk += len(emails_to_check) * 5
    for em, hibp in hibp_results.items():
        risk += len(hibp.get("breaches", [])) * 10
    risk += len(registered_domains) * 3
    risk += (20 if github.get("exists") else 0)
    risk += (10 if gravatar.get("has_gravatar") else 0)
    risk += (5  if maigret.get("raw_count", 0) > 50 else 0)
    risk += (8  if holehe.get("sites_count", 0) > 10 else 0)
    risk = min(100, risk)

    # Flags
    flags = []
    total_platforms = len(found)
    if total_platforms > 50:
        flags.append(f"🔴 Extreme digital footprint — active on {total_platforms} platforms")
    elif total_platforms > 20:
        flags.append(f"🟠 High digital footprint — active on {total_platforms} platforms")
    if any(hibp_results.get(em, {}).get("breaches") for em in hibp_results):
        total_breaches = sum(len(v.get("breaches", [])) for v in hibp_results.values())
        flags.append(f"🚨 Email(s) found in {total_breaches} data breach(es)")
    if github.get("emails_found"):
        flags.append(f"📧 {len(github['emails_found'])} email(s) leaked via GitHub commits")
    if pastes.get("mentions"):
        flags.append(f"⚠️  Username mentioned on paste site(s)")
    if registered_domains:
        flags.append(f"🌐 Owns domain(s): {', '.join(d['domain'] for d in registered_domains)}")
    if github.get("profile", {}).get("twitter"):
        flags.append(f"🐦 Twitter/X linked on GitHub: @{github['profile']['twitter']}")
    if gravatar.get("has_gravatar"):
        name_on_gravatar = gravatar.get("profile", {}).get("display_name") or "unknown"
        flags.append(f"🖼️  Gravatar account found — display name: {name_on_gravatar}")
    if gravatar.get("profile", {}).get("accounts"):
        linked = [a["domain"] for a in gravatar["profile"]["accounts"][:3]]
        flags.append(f"🔗 Gravatar links to: {', '.join(linked)}")
    if maigret.get("linked_usernames"):
        flags.append(f"👤 maigret found linked usernames: {', '.join(maigret['linked_usernames'][:5])}")
    if maigret.get("linked_emails"):
        flags.append(f"📧 maigret found linked emails: {', '.join(maigret['linked_emails'][:3])}")
    if holehe.get("sites_count", 0) > 0:
        flags.append(f"📨 Email registered on {holehe['sites_count']} site(s) via holehe")
    if phone_intel.get("valid") and phone_intel.get("number_type") == "VoIP":
        flags.append(f"📵 Phone number is VoIP — possible anonymity tool")
    if phoneinfoga.get("spam_score") and phoneinfoga["spam_score"] > 30:
        flags.append(f"⚠️  Phone spam score: {phoneinfoga['spam_score']}%")

    return {
        "stage": "social_search",
        "username": username,
        "emails_checked": list(emails_to_check),
        "risk_score": risk,
        "flags": flags,
        "summary": {
            "platforms_checked": len(platform_results),
            "platforms_found": len(found),
            "platforms_not_found": len(not_found),
            "platforms_error": len(errors),
            "maigret_found": maigret.get("raw_count", 0),
            "holehe_found": holehe.get("sites_count", 0),
        },
        "found_platforms": found,
        "by_category": by_category,
        "github": github,
        "breach_data": hibp_results,
        "paste_mentions": pastes,
        "domains": domains,
        "registered_domains": registered_domains,
        "gravatar": gravatar,
        "email_permutations": email_permutations,
        "phone_intel": phone_intel,
        "phoneinfoga": phoneinfoga,
        "maigret": maigret,
        "holehe": holehe,
    }


if __name__ == "__main__":
    import sys
    username = sys.argv[1] if len(sys.argv) > 1 else input("Username to search: ").strip()
    email    = sys.argv[2] if len(sys.argv) > 2 else ""
    phone    = sys.argv[3] if len(sys.argv) > 3 else ""
    name     = sys.argv[4] if len(sys.argv) > 4 else ""
    result   = search(username, email=email, phone=phone, name=name)

    print(f"\n=== Results for '{username}' ===")
    s = result["summary"]
    print(f"Found on {s['platforms_found']} / {s['platforms_checked']} platforms"
          f" (+{s['maigret_found']} maigret, +{s['holehe_found']} holehe)")
    print(f"Risk score: {result['risk_score']}/100")
    print("\nFlags:")
    for f in result["flags"]:
        print(f"  {f}")
    print("\nFound on:")
    for p in result["found_platforms"]:
        src = f" [{p.get('source','')}]" if p.get("source") else ""
        print(f"  [{p['category']:12}] {p['platform']:<20} {p['url']}{src}")
    if result["registered_domains"]:
        print("\nRegistered domains:")
        for d in result["registered_domains"]:
            print(f"  {d['domain']}")
    if result["gravatar"].get("has_gravatar"):
        print(f"\nGravatar: {result['gravatar']['avatar_url']}")
        if result["gravatar"]["profile"].get("display_name"):
            print(f"  Name: {result['gravatar']['profile']['display_name']}")
    if result["phone_intel"].get("valid"):
        pi = result["phone_intel"]
        print(f"\nPhone: {pi['international_format']} | {pi['country']} | {pi['number_type']}"
              + (f" | {pi['carrier']}" if pi.get("carrier") else ""))
    if result["email_permutations"]:
        print(f"\nEmail permutations ({len(result['email_permutations'])}):")
        for e in result["email_permutations"][:10]:
            print(f"  {e}")
