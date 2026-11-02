"""Fetch CC0 sounds for the mangarr-sounds packs.

Freesound: search with the CC0 filter, then open each sound's page and keep
it only if the page's licence link is CC0 (publicdomain/zero/1.0) and no
other Creative Commons licence. The HQ preview (MP3) is downloaded.

Writes downloads/<source>/<id>.<ext> and downloads/manifest.json with each
sound's source page, author, title and licence as checked.
"""
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the repository
DL = os.path.join(ROOT, "downloads")
UA = {"User-Agent": "Mozilla/5.0 (mangarr-sounds builder)"}
CC0 = "creativecommons.org/publicdomain/zero/1.0"

# pack -> list of (query, kind, category, icon, count, min seconds, max seconds)
PLAN = {
    "weather": [
        ("rain loop", "ambience", "weather", "cloud-rain", 2, 30, 900),
        ("heavy rain", "ambience", "weather", "cloud-rain", 1, 30, 900),
        ("rain on window", "ambience", "weather", "droplets", 1, 30, 900),
        ("wind howling", "ambience", "weather", "wind", 2, 20, 900),
        ("thunderstorm", "ambience", "weather", "cloud-lightning", 1, 30, 900),
        ("blizzard", "ambience", "weather", "snowflake", 1, 20, 900),
        ("thunder", "sfx", "weather", "cloud-lightning", 3, 2, 20),
        ("footsteps snow", "sfx", "body", "footprints", 1, 1, 20),
    ],
    "city": [
        ("city street ambience", "ambience", "city", "building", 2, 30, 900),
        ("traffic ambience", "ambience", "city", "car", 1, 30, 900),
        ("crowd market", "ambience", "city", "users", 1, 30, 900),
        ("cafe ambience", "ambience", "city", "users", 1, 30, 900),
        ("train station", "ambience", "city", "train-front", 1, 30, 900),
        ("school hallway", "ambience", "city", "users", 1, 20, 900),
        ("car horn", "sfx", "city", "car", 2, 0.3, 6),
        ("crowd cheer", "sfx", "voices", "users", 1, 1, 15),
    ],
    "nature": [
        ("forest birds", "ambience", "nature", "trees", 2, 30, 900),
        ("ocean waves", "ambience", "water", "waves", 2, 30, 900),
        ("river stream", "ambience", "water", "droplets", 2, 30, 900),
        ("night crickets", "ambience", "nature", "trees", 1, 30, 900),
        ("campfire", "ambience", "nature", "flame", 1, 20, 900),
        ("underwater", "ambience", "water", "waves", 1, 20, 900),
        ("bird chirp", "sfx", "nature", "bird", 2, 0.5, 10),
        ("owl", "sfx", "nature", "bird", 1, 0.5, 10),
    ],
    "combat": [
        ("battle ambience", "ambience", "combat", "swords", 1, 20, 900),
        ("sword clash", "sfx", "combat", "swords", 3, 0.2, 5),
        ("punch", "sfx", "combat", "zap", 2, 0.1, 3),
        ("explosion", "sfx", "combat", "bomb", 2, 0.5, 10),
        ("arrow", "sfx", "combat", "zap", 1, 0.2, 4),
        ("sword unsheath", "sfx", "combat", "swords", 1, 0.2, 4),
        ("gunshot", "sfx", "combat", "zap", 1, 0.1, 4),
    ],
    "objects": [
        ("clock ticking", "ambience", "objects", "clock", 1, 20, 900),
        ("room tone", "ambience", "objects", "audio-lines", 1, 30, 900),
        ("door open close", "sfx", "objects", "door-open", 2, 0.3, 6),
        ("door knock", "sfx", "objects", "door-open", 1, 0.3, 6),
        ("bell", "sfx", "objects", "bell", 2, 0.5, 15),
        ("footsteps wood", "sfx", "body", "footprints", 2, 1, 15),
        ("glass break", "sfx", "objects", "wine", 1, 0.3, 6),
        ("glass clink", "sfx", "objects", "wine", 1, 0.2, 4),
        ("heartbeat", "sfx", "body", "heart-pulse", 1, 1, 15),
    ],
}


# a result's title must have one of these words (by query), so popular but
# unrelated sounds stay out
MUST = {
    "rain loop": ["rain"], "heavy rain": ["rain"], "rain on window": ["rain"], "wind howling": ["wind"], "thunderstorm": ["thunder", "storm"],
    "blizzard": ["blizzard", "snow", "wind"], "thunder": ["thunder"], "footsteps snow": ["snow"],
    "city street ambience": ["city", "street"], "traffic ambience": ["traffic"], "crowd market": ["market", "crowd", "bazaar"], "cafe ambience": ["cafe", "café", "coffee", "restaurant"],
    "train station": ["station", "train"], "school hallway": ["school", "hallway", "classroom"], "car horn": ["horn"], "crowd cheer": ["cheer", "applause"],
    "forest birds": ["forest", "bird"], "ocean waves": ["ocean", "wave", "sea"], "river stream": ["river", "stream", "creek", "brook"], "night crickets": ["cricket", "night", "insect"],
    "campfire": ["fire"], "underwater": ["underwater"], "bird chirp": ["bird", "chirp", "tweet"], "owl": ["owl"],
    "battle ambience": ["battle", "war"], "sword clash": ["sword", "clash", "blade"], "punch": ["punch"], "explosion": ["explosion", "explode", "blast"], "arrow": ["arrow", "bow"],
    "sword unsheath": ["sword", "unsheath", "sheath"], "gunshot": ["gun", "shot"],
    "clock ticking": ["clock", "tick"], "room tone": ["room"], "door open close": ["door"], "door knock": ["knock"], "bell": ["bell"],
    "footsteps wood": ["footstep", "step"], "glass break": ["glass", "shatter"], "glass clink": ["glass", "clink"], "heartbeat": ["heart"],
}


def fits(query, title):
    t = title.lower()
    # music comes from Spotify: no music in packs
    if any(w in t for w in ("music", "soundtrack", "song", "melody", "theme")):
        return False
    return any(w in t for w in MUST.get(query, query.split()))


def get(url, binary=False, head=0):
    for attempt in range(4):
        extra = ["-r", f"0-{head}"] if head else []
        r = subprocess.run(["curl", "-sSfL", "--retry", "3", *extra, "-A", UA["User-Agent"], url], capture_output=True)
        if r.returncode == 0:
            return r.stdout if binary else r.stdout.decode("utf-8", "replace")
        time.sleep(2 ** attempt)
    raise RuntimeError(f"{url}: {r.stderr.decode()}")


def search(query, page=1):
    q = urllib.parse.urlencode({"q": query, "f": 'license:"Creative Commons 0"', "s": "Downloads (most first)", "page": page})
    s = get("https://freesound.org/search/?" + q)
    out = []
    for m in re.finditer(r'data-sound-id="(\d+)"(.{0,3000}?)data-duration="([\d.]+)"', s, re.S):
        block = m.group(2)
        title = re.search(r'data-title="([^"]*)"', block)
        user = re.search(r'data-username="([^"]*)"', block)
        out.append({"id": int(m.group(1)), "duration": float(m.group(3)), "title": html.unescape(title.group(1)) if title else "", "user": user.group(1) if user else ""})
    return out


def check_page(sid, user):
    url = f"https://freesound.org/people/{user}/sounds/{sid}/"
    s = get(url)
    licences = set(re.findall(r"creativecommons\.org/[a-z]+(?:/[a-z-]+)*/[\d.]+", s))
    hq = re.search(r"https://cdn\.freesound\.org/previews/\d+/\d+_\d+-hq\.mp3", s)
    ok = licences == {CC0} and hq is not None
    return url, ok, sorted(licences), hq.group(0) if hq else ""


def main():
    os.makedirs(os.path.join(DL, "freesound"), exist_ok=True)
    manifest_path = os.path.join(DL, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {"sounds": [], "rejected": []}
    # drop what an earlier run took that doesn't fit its query
    manifest["sounds"] = [s for s in manifest["sounds"] if fits(s["query"], s["title"])]
    taken = {s["id"] for s in manifest["sounds"]} | {r["id"] for r in manifest["rejected"]}
    only = set(sys.argv[1:])
    for pack, items in PLAN.items():
        if only and pack not in only:
            continue
        for query, kind, category, icon, count, lo, hi in items:
            have = [s for s in manifest["sounds"] if s["pack"] == pack and s["query"] == query]
            need = count - len(have)
            page = 1
            while need > 0 and page <= 3:
                for r in search(query, page):
                    if need <= 0:
                        break
                    if r["id"] in taken or not (lo <= r["duration"] <= hi) or not fits(query, r["title"]):
                        continue
                    url, ok, licences, hq = check_page(r["id"], r["user"])
                    if not ok:
                        manifest["rejected"].append({"id": r["id"], "url": url, "licences": licences})
                        continue
                    path = os.path.join(DL, "freesound", f"{r['id']}.mp3")
                    if not os.path.exists(path):
                        with open(path, "wb") as f:
                            # a loop needs about 80 s: about 1.6 MB of the 128 kbps preview
                            f.write(get(hq, binary=True, head=1_700_000 if kind == "ambience" else 0))
                    manifest["sounds"].append({
                        "id": r["id"], "source": "freesound", "pack": pack, "query": query, "kind": kind, "category": category, "icon": icon,
                        "title": r["title"], "author": r["user"], "url": url, "licence": "CC0-1.0", "licence_checked": time.strftime("%Y-%m-%d"),
                        "duration": r["duration"], "file": f"freesound/{r['id']}.mp3",
                    })
                    taken.add(r["id"])
                    need -= 1
                    print(f"{pack}: {query}: {r['title']} ({r['duration']:.0f}s) {url}", flush=True)
                    json.dump(manifest, open(manifest_path, "w"), indent=1)
                    time.sleep(0.5)
                page += 1
            if need > 0:
                print(f"{pack}: {query}: only found {count - need} of {count}", flush=True)
    json.dump(manifest, open(manifest_path, "w"), indent=1)


if __name__ == "__main__":
    main()
