#!/usr/bin/env python3
"""Builds the Sean's Backyard site from the files in content/ into _site/.

Run:  python build.py
Needs: jinja2, markdown, pyyaml (see requirements.txt)
"""
import datetime
import re
import shutil
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
OUT = ROOT / "_site"

FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*(?:\n(.*))?$", re.DOTALL)


# ---------- reading content ----------

def to_html(text):
    text = (text or "").strip()
    if not text:
        return ""
    return Markup(markdown.markdown(text, extensions=["extra", "sane_lists"]))


def load_entry(path):
    text = path.read_text(encoding="utf-8").lstrip("﻿")
    meta, body = {}, text
    match = FRONT_MATTER.match(text)
    if match:
        loaded = yaml.safe_load(match.group(1))
        meta = loaded if isinstance(loaded, dict) else {}
        body = match.group(2) or ""
    entry = dict(meta)
    entry["slug"] = path.stem
    entry["body_html"] = to_html(body)
    return entry


def load_collection(name):
    folder = CONTENT / name
    if not folder.is_dir():
        return []
    return [load_entry(p) for p in sorted(folder.glob("*.md"))]


def load_yaml(name):
    path = CONTENT / name
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def ref(value):
    """A link to another entry, however the admin screen saved it -> its slug."""
    if not value:
        return ""
    if isinstance(value, dict):
        value = value.get("slug") or value.get("name") or value.get("path") or ""
    value = str(value).strip().replace("\\", "/").rsplit("/", 1)[-1]
    return re.sub(r"\.(md|markdown|ya?ml)$", "", value)


def to_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None


def to_number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def show_number(value):
    """Blank stays blank; 12.0 shows as 12; 1432.5 stays 1432.5."""
    if value is None or value == "":
        return ""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(number)) if number == int(number) else f"{number:g}"


def as_list(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


# ---------- shaping content ----------

def build_data():
    settings = load_yaml("settings.yml")
    people = {p["slug"]: p for p in load_collection("people")}
    leagues = load_collection("leagues")
    seasons = load_collection("seasons")
    posts = load_collection("posts")
    records = as_list(load_yaml("records.yml").get("records"))

    def person(slug_or_name):
        """Name and profile link for someone, even if they have no profile yet."""
        slug = ref(slug_or_name)
        if not slug:
            return None
        if slug in people:
            return {"slug": slug, "name": people[slug].get("title") or slug, "has_page": True}
        return {"slug": slug, "name": str(slug_or_name).strip(), "has_page": False}

    league_by_slug = {league["slug"]: league for league in leagues}
    for league in leagues:
        league["title"] = league.get("title") or league["slug"]
        league["is_game"] = league.get("format") == "game"
        league["seasons"] = []
        league["posts"] = []
    leagues.sort(key=lambda l: (to_number(l.get("order"), 999), l["title"]))

    for season in seasons:
        season["title"] = season.get("title") or season["slug"]
        season["league_slug"] = ref(season.get("league"))
        season["league"] = league_by_slug.get(season["league_slug"])
        season["order_value"] = to_number(season.get("order"))
        season["champion_person"] = person(season.get("champion"))
        standings = []
        for position, row in enumerate(as_list(season.get("standings")), start=1):
            wins, losses, ties = row.get("wins"), row.get("losses"), row.get("ties")
            record = ""
            if wins not in (None, "") or losses not in (None, ""):
                record = f"{show_number(wins) or 0}–{show_number(losses) or 0}"
                if to_number(ties) > 0:
                    record += f"–{show_number(ties)}"
            standings.append({
                "position": position,
                "team": row.get("team") or "",
                "manager": person(row.get("manager")),
                "record": record,
                "points_for": show_number(row.get("points_for")),
                "points_against": show_number(row.get("points_against")),
            })
        season["standings_rows"] = standings
        season["cast_rows"] = [
            {"person": person(row.get("person")), "role": row.get("role") or "", "result": row.get("result") or ""}
            for row in as_list(season.get("cast"))
        ]
        if season["league"]:
            season["league"]["seasons"].append(season)

    for league in leagues:
        league["seasons"].sort(key=lambda s: (s["order_value"], s["title"]), reverse=True)
        league["latest"] = league["seasons"][0] if league["seasons"] else None
        league["reigning"] = next((s for s in league["seasons"] if s["champion_person"]), None)

    for post in posts:
        post["title"] = post.get("title") or post["slug"]
        post["date_value"] = to_date(post.get("date")) or to_date(post["slug"])
        post["date_text"] = post["date_value"].strftime("%b %-d, %Y") if post["date_value"] else ""
        post["league"] = league_by_slug.get(ref(post.get("league")))
        post["tag"] = post.get("category") or (post["league"]["kind"] if post["league"] and post["league"].get("kind") else "Post")
        if post["league"]:
            post["league"]["posts"].append(post)
    posts.sort(key=lambda p: (p["date_value"] or datetime.date.min, p["slug"]), reverse=True)
    for league in leagues:
        league["posts"].sort(key=lambda p: (p["date_value"] or datetime.date.min, p["slug"]), reverse=True)

    # Who has played in what, and who has won what.
    history = {}

    def note(slug_or_name, kind, season):
        who = person(slug_or_name)
        if not who or not season["league"]:
            return
        entry = history.setdefault(who["slug"], {"person": who, "titles": [], "played": [], "title_slugs": []})
        if all(existing["slug"] != season["slug"] for existing in entry[kind]):
            entry[kind].append(season)
            if kind == "titles":
                entry["title_slugs"].append(season["slug"])

    for season in sorted(seasons, key=lambda s: s["order_value"], reverse=True):
        note(season.get("champion"), "titles", season)
        note(season.get("champion"), "played", season)
        for row in as_list(season.get("standings")):
            note(row.get("manager"), "played", season)
        for row in as_list(season.get("cast")):
            note(row.get("person"), "played", season)

    title_table = sorted(
        (h for h in history.values() if h["titles"]),
        key=lambda h: (-len(h["titles"]), h["person"]["name"].lower()),
    )

    people_list = sorted(people.values(), key=lambda p: (p.get("title") or p["slug"]).lower())
    for p in people_list:
        p["title"] = p.get("title") or p["slug"]
        p["history"] = history.get(p["slug"], {"titles": [], "played": [], "title_slugs": []})

    for record in records:
        record["holder_person"] = person(record.get("holder"))
        record["league"] = league_by_slug.get(ref(record.get("league")))

    return {
        "site": {
            "title": settings.get("title") or "Sean's Backyard",
            "headline": settings.get("headline") or "",
            "tagline": settings.get("tagline") or "",
            "footer": settings.get("footer") or "",
            "admin_url": settings.get("admin_url") or "",
        },
        "leagues": leagues,
        "seasons": seasons,
        "posts": posts,
        "people": people_list,
        "records": records,
        "title_table": title_table,
    }


# ---------- writing pages ----------

def main():
    data = build_data()
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(ROOT / "static", OUT / "assets")
    media = ROOT / "media"
    if media.is_dir():
        shutil.copytree(media, OUT / "media")
    (OUT / ".nojekyll").write_text("")

    count = 0

    def page(template, out_path, section, **context):
        nonlocal count
        target = OUT / out_path / "index.html" if out_path else OUT / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        depth = len(Path(out_path).parts) if out_path else 0
        root = "../" * depth
        html = env.get_template(template).render(root=root, section=section, **data, **context)
        # Uploaded images are saved as /media/...; point them at this site's own folder.
        html = html.replace('="/media/', f'="{root}media/')
        target.write_text(html, encoding="utf-8")
        count += 1

    page("home.html", "", "home")
    page("leagues.html", "leagues", "leagues")
    for league in data["leagues"]:
        page("league.html", f"leagues/{league['slug']}", "leagues", league=league, season=league["latest"])
    for season in data["seasons"]:
        if season["league"]:
            page("league.html", f"leagues/{season['league']['slug']}/{season['slug']}", "leagues",
                 league=season["league"], season=season, season_page=True)
    page("records.html", "records", "records")
    page("people.html", "people", "people")
    for someone in data["people"]:
        page("person.html", f"people/{someone['slug']}", "people", someone=someone)
    page("blog.html", "blog", "blog")
    for post in data["posts"]:
        page("post.html", f"blog/{post['slug']}", "blog", post=post)

    print(f"Built {count} pages into {OUT.name}/")


if __name__ == "__main__":
    main()
