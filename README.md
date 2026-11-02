# mangarr-sounds

Sound packs for [Mangarr](https://github.com/Asion001/mangarr) soundtracks: ambience loops and sound effects that play while you read, layered over the music of a mood.

| Pack | What's in it |
|---|---|
| Weather | Rain, wind, thunder and snow |
| City & crowds | Streets, traffic, markets, cafés, stations |
| Nature & water | Forest, ocean, rivers, night insects, campfire |
| Combat & impacts | Swords, punches, explosions, hits |
| Everyday objects | Doors, bells, footsteps, glass, clocks |

## Installing

Mangarr lists these packs under **Settings → Soundtracks → Spotify & packs → From the catalog**. The catalog is published with each release:

```
https://github.com/Asion001/mangarr-sounds/releases/latest/download/catalog.json
```

You can also download a pack's zip from the [releases](https://github.com/Asion001/mangarr-sounds/releases) and upload it there.

## Format

Each pack is a zip with a `pack.json` and its sounds (Ogg/Opus):

```json
{
  "id": "mangarr-weather",
  "version": "1.0.0",
  "name": "Weather",
  "license": "CC0-1.0",
  "tracks": [
    { "file": "sounds/rain-123.ogg", "kind": "ambience", "category": "weather", "icon": "cloud-rain",
      "title": "Rain", "tags": ["rain"], "license": "CC0-1.0", "attribution": "Author (Freesound)",
      "source_url": "https://freesound.org/…", "gain_db": -4.5 }
  ],
  "scenes": [
    { "name": "Rainy night", "mood": "melancholy",
      "ambience": [{ "file": "sounds/rain-123.ogg", "volume": 0.7 }],
      "sfx": [{ "file": "sounds/thunder-456.ogg", "label": "Thunder" }] }
  ]
}
```

- `kind` is `ambience` (looped) or `sfx` (played once).
- `category` is one of weather, water, nature, city, objects, combat, body, magic, voices, other.
- `gain_db` brings each sound to a common loudness.
- Ambience loops are cut to about 75 seconds and made seamless: their last seconds crossfade into their first.
- `scenes` are optional ready-made scenes. `mood` names one of Mangarr's built-in moods.

`catalog.json` lists the packs with their zip (relative to the catalog), size, sound count and SHA-256.

## Licences

Every sound is **CC0** (public domain dedication). Each one's licence was checked on its source page when it was downloaded, and anything that wasn't clearly CC0 was skipped. Sounds come from [Freesound](https://freesound.org) (searched with the CC0 filter; HQ previews) and [Kenney](https://kenney.nl). Each sound keeps its own licence and source in `pack.json`, and [CREDITS.md](CREDITS.md) lists them all with links. Crediting the authors isn't required, but please do.

The scripts in `tools/` are under the MIT licence (see [LICENSE](LICENSE)).

## Rebuilding

`tools/fetch.py` finds and checks CC0 sounds on Freesound, and `tools/build.py` turns them into packs (it needs `ffmpeg` with libopus). Kenney's packs are downloaded by hand from their pages into `downloads/kenney/`.
