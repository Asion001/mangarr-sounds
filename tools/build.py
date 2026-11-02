"""Build the mangarr-sounds packs from the checked downloads.

Every sound becomes Ogg/Opus. Ambience is cut to at most LOOP_MAX seconds
and made into a seamless loop (its last seconds crossfade into its first);
each track gets a gain_db that brings it to a common loudness. Writes
repo/packs/<id>/pack.json and sounds, repo/dist/<id>.zip, repo/dist/catalog.json
and repo/CREDITS.md.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the repository
DL = os.path.join(ROOT, "downloads")
REPO = ROOT
VERSION = "1.0.0"
LOOP_MAX = 75
XFADE = 2.5
TARGET = {"ambience": -28.0, "sfx": -20.0}
SOURCE = "https://github.com/Asion001/mangarr-sounds"

PACKS = {
    "weather": ("mangarr-weather", "Weather", "Rain, wind, thunder and snow."),
    "city": ("mangarr-city", "City & crowds", "Streets, traffic, markets, cafés and stations."),
    "nature": ("mangarr-nature", "Nature & water", "Forest, ocean, rivers, night insects and campfire."),
    "combat": ("mangarr-combat", "Combat & impacts", "Swords, punches, explosions and hits."),
    "objects": ("mangarr-objects", "Everyday objects", "Doors, bells, footsteps, glass and clocks."),
}

KENNEY = {
    "impact": ("Impact Sounds", "https://kenney.nl/assets/impact-sounds"),
    "rpg": ("RPG Audio", "https://kenney.nl/assets/rpg-audio"),
}

# pack -> (kenney pack, file, kind, category, icon, title)
KENNEY_PICKS = {
    "weather": [
        ("impact", "footstep_snow_000.ogg", "sfx", "body", "footprints", "Steps in snow"),
        ("impact", "footstep_snow_002.ogg", "sfx", "body", "footprints", "Steps in snow 2"),
    ],
    "combat": [
        ("impact", "impactPunch_heavy_000.ogg", "sfx", "combat", "zap", "Heavy punch"),
        ("impact", "impactPunch_medium_000.ogg", "sfx", "combat", "zap", "Punch"),
        ("impact", "impactMetal_heavy_000.ogg", "sfx", "combat", "swords", "Metal hit"),
        ("impact", "impactMetal_heavy_002.ogg", "sfx", "combat", "swords", "Metal hit 2"),
        ("impact", "impactPlate_heavy_000.ogg", "sfx", "combat", "swords", "Armour hit"),
        ("impact", "impactWood_heavy_000.ogg", "sfx", "combat", "zap", "Wood hit"),
        ("rpg", "drawKnife1.ogg", "sfx", "combat", "swords", "Draw a blade"),
        ("rpg", "knifeSlice.ogg", "sfx", "combat", "swords", "Slash"),
        ("rpg", "chop.ogg", "sfx", "combat", "swords", "Chop"),
    ],
    "objects": [
        ("rpg", "doorOpen_1.ogg", "sfx", "objects", "door-open", "Door opens"),
        ("rpg", "doorClose_1.ogg", "sfx", "objects", "door-open", "Door closes"),
        ("rpg", "creak1.ogg", "sfx", "objects", "door-open", "Creak"),
        ("rpg", "footstep00.ogg", "sfx", "body", "footprints", "Footstep"),
        ("rpg", "footstep04.ogg", "sfx", "body", "footprints", "Footstep 2"),
        ("rpg", "bookFlip1.ogg", "sfx", "objects", "key", "Page turn"),
        ("rpg", "handleCoins.ogg", "sfx", "objects", "key", "Coins"),
        ("rpg", "metalLatch.ogg", "sfx", "objects", "key", "Latch"),
        ("impact", "impactGlass_light_000.ogg", "sfx", "objects", "wine", "Glass tap"),
        ("impact", "impactGlass_medium_000.ogg", "sfx", "objects", "wine", "Glass knock"),
        ("impact", "impactBell_heavy_000.ogg", "sfx", "objects", "bell", "Bell hit"),
    ],
}

# ready-made scenes: (name, mood slug, [(query or kenney file, volume)], [(query or kenney file, label)])
SCENES = {
    "weather": [
        ("Rainy night", "melancholy", [("rain loop", 0.7), ("rain on window", 0.4)], [("thunder", "Thunder")]),
        ("Storm", "tense", [("thunderstorm", 0.8), ("wind howling", 0.5)], [("thunder", "Thunder")]),
        ("Snowfall", "calm", [("blizzard", 0.4)], [("footstep_snow_000.ogg", "Steps in snow")]),
    ],
    "city": [
        ("Busy street", "comedy", [("city street ambience", 0.6), ("traffic ambience", 0.3)], [("car horn", "Horn")]),
        ("Café", "romance", [("cafe ambience", 0.6)], []),
        ("School day", "comedy", [("school hallway", 0.6)], []),
        ("Station", "melancholy", [("train station", 0.6)], []),
    ],
    "nature": [
        ("Seaside", "calm", [("ocean waves", 0.7)], [("bird chirp", "Gull")]),
        ("Forest", "calm", [("forest birds", 0.6), ("river stream", 0.3)], [("bird chirp", "Bird")]),
        ("Night forest", "mystery", [("night crickets", 0.6)], [("owl", "Owl")]),
        ("Campfire", "calm", [("campfire", 0.7), ("night crickets", 0.25)], []),
    ],
    "combat": [
        ("Battlefield", "action", [("battle ambience", 0.6)], [("sword clash", "Clash"), ("impactPunch_heavy_000.ogg", "Punch"), ("explosion", "Explosion"), ("arrow", "Arrow")]),
        ("Duel", "tense", [], [("sword clash", "Clash"), ("drawKnife1.ogg", "Draw"), ("knifeSlice.ogg", "Slash"), ("impactMetal_heavy_000.ogg", "Hit")]),
    ],
    "objects": [
        ("Quiet room", "calm", [("clock ticking", 0.5), ("room tone", 0.3)], [("doorOpen_1.ogg", "Door"), ("footstep00.ogg", "Step"), ("bell", "Bell"), ("glass clink", "Glass")]),
        ("Haunted house", "horror", [("room tone", 0.5)], [("creak1.ogg", "Creak"), ("door knock", "Knock"), ("heartbeat", "Heartbeat"), ("glass break", "Glass breaks")]),
    ],
}


def run(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(" ".join(args) + "\n" + r.stderr[-2000:])
    return r


def duration(path):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path).stdout.strip())


def loudness(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", err)
    return float(m[-1]) if m else -23.0


def peak(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"max_volume:\s+(-?[\d.]+) dB", err)
    return float(m.group(1)) if m else 0.0


def gain_for(path, kind):
    # effects by their peak (loudness needs more than a short hit to measure),
    # ambience by loudness
    g = (-6.0 - peak(path)) if kind == "sfx" else (TARGET["ambience"] - loudness(path))
    return max(-30.0, min(12.0, round(g, 1)))


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "sound"


def encode(src, dst, kind):
    if kind == "ambience":
        d = min(duration(src), LOOP_MAX + XFADE)
        body = d - XFADE
        # the loop: [xfade(tail, head)] + middle; the end of the middle runs into the blend's start
        flt = (
            f"[0:a]atrim=0:{d},asetpts=N/SR/TB,aformat=sample_rates=48000:channel_layouts=stereo,asplit=3[a][b][c];"
            f"[a]atrim=0:{XFADE},asetpts=N/SR/TB[head];"
            f"[b]atrim={XFADE}:{body},asetpts=N/SR/TB[mid];"
            f"[c]atrim={body}:{d},asetpts=N/SR/TB[tail];"
            f"[tail][head]acrossfade=d={XFADE}:c1=tri:c2=tri[xf];"
            f"[xf][mid]concat=n=2:v=0:a=1[out]"
        )
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-filter_complex", flt, "-map", "[out]", "-c:a", "libopus", "-b:a", "96k", "-vbr", "on", dst)
    else:
        run("ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-af", "aformat=sample_rates=48000", "-c:a", "libopus", "-b:a", "96k", "-vbr", "on", dst)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    manifest = json.load(open(os.path.join(DL, "manifest.json")))
    dist = os.path.join(REPO, "dist")
    os.makedirs(dist, exist_ok=True)
    catalog, credits = [], []
    only = set(sys.argv[1:])
    for key, (pid, name, desc) in PACKS.items():
        if only and key not in only:
            continue
        out = os.path.join(REPO, "packs", pid)
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(os.path.join(out, "sounds"))
        tracks, by_ref = [], {}
        items = [s for s in manifest["sounds"] if s["pack"] == key]
        for s in items:
            src = os.path.join(DL, s["file"])
            fname = f"sounds/{slug(s['title'].rsplit('.', 1)[0])}-{s['id']}.ogg"
            encode(src, os.path.join(out, fname), s["kind"])
            gain = gain_for(os.path.join(out, fname), s["kind"])
            title = re.sub(r"\.(wav|mp3|flac|aiff?|ogg)$", "", s["title"], flags=re.I).replace("_", " ").strip()
            tracks.append({"file": fname, "kind": s["kind"], "category": s["category"], "icon": s["icon"], "title": title[:80], "tags": [s["query"]],
                           "license": "CC0-1.0", "attribution": f"{s['author']} (Freesound)", "source_url": s["url"], "gain_db": gain})
            by_ref.setdefault(s["query"], []).append(fname)
            credits.append((name, title, s["author"], "Freesound", s["url"], s["licence_checked"]))
        for kp, f, kind, cat, icon, title in KENNEY_PICKS.get(key, []):
            found = [os.path.join(dp, fn) for dp, _, fns in os.walk(os.path.join(DL, "kenney", kp)) for fn in fns if fn == f]
            if not found:
                print("missing", kp, f)
                continue
            fname = f"sounds/{slug(title)}-kenney.ogg"
            encode(found[0], os.path.join(out, fname), kind)
            gain = gain_for(os.path.join(out, fname), kind)
            pname, purl = KENNEY[kp]
            tracks.append({"file": fname, "kind": kind, "category": cat, "icon": icon, "title": title, "tags": [], "license": "CC0-1.0",
                           "attribution": f"Kenney ({pname})", "source_url": purl, "gain_db": gain})
            by_ref[f] = [fname]
            credits.append((name, title, "Kenney", f"Kenney {pname}", purl, "2026-11-02"))
        scenes = []
        for sname, mood, amb, sfx in SCENES.get(key, []):
            used = {}

            def pick(ref):
                files = by_ref.get(ref, [])
                i = used.get(ref, 0)
                used[ref] = i + 1
                return files[i % len(files)] if files else None

            a = [{"file": f, "volume": v} for ref, v in amb if (f := pick(ref))]
            x = [{"file": f, "label": lab} for ref, lab in sfx if (f := pick(ref))]
            if a or x:
                scenes.append({"name": sname, "mood": mood, "ambience": a[:4], "sfx": x[:8]})
        pack = {"id": pid, "version": VERSION, "name": name, "description": desc, "license": "CC0-1.0", "source_url": SOURCE, "tracks": tracks, "scenes": scenes}
        json.dump(pack, open(os.path.join(out, "pack.json"), "w"), indent=2, ensure_ascii=False)
        zpath = os.path.join(dist, f"{pid}.zip")
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_STORED) as z:
            z.write(os.path.join(out, "pack.json"), f"{pid}/pack.json")
            for t in tracks:
                z.write(os.path.join(out, t["file"]), f"{pid}/{t['file']}")
        size = os.path.getsize(zpath)
        catalog.append({"id": pid, "name": name, "version": VERSION, "description": desc, "license": "CC0-1.0", "url": f"{pid}.zip", "size": size, "sounds": len(tracks), "sha256": sha256(zpath)})
        print(f"{pid}: {len(tracks)} sounds, {len([t for t in tracks if t['kind'] == 'ambience'])} ambience, {len(scenes)} scenes, {size / 1e6:.1f} MB", flush=True)
    if not only:
        json.dump({"packs": catalog}, open(os.path.join(dist, "catalog.json"), "w"), indent=2, ensure_ascii=False)
        lines = ["# Credits", "", "Every sound here is CC0 (public domain dedication). Licences were checked on each sound's source page when it was downloaded; the links below lead there.", ""]
        for pname in [p[1] for p in PACKS.values()]:
            lines += [f"## {pname}", "", "| Sound | Author | Source | Licence checked |", "|---|---|---|---|"]
            for pk, title, author, src, url, when in credits:
                if pk == pname:
                    lines.append(f"| {title.replace('|', '/')} | {author} | [{src}]({url}) | CC0 1.0, {when} |")
            lines.append("")
        open(os.path.join(REPO, "CREDITS.md"), "w").write("\n".join(lines))


if __name__ == "__main__":
    main()
