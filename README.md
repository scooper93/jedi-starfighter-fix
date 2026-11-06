# Star Wars: Jedi Starfighter – "Hammer and Anvil" fix for PCSX2

Fixes the Mission 7 ("Hammer and Anvil") softlock when playing the PS2 version
in PCSX2, where the *Kethor* flies off into empty space instead of ramming the
shield projector and the mission can never be completed.

Related PCSX2 issue: [#1927](https://github.com/PCSX2/pcsx2/issues/1927)

Tested on the USA disc (SLUS-20293) in PCSX2. Other regions are untested and the
patcher will refuse to touch them (see [Safety](#safety)).

## Quick start

1. Make a copy of your own **uncompressed** ISO of the USA disc (CSO/CHD images
   are not supported, since the patcher edits bytes in place).
2. Run:

   ```
   python3 patch_hammer_anvil.py "Star Wars - Jedi Starfighter (USA).iso"
   ```

3. Play Mission 7 as normal.

Requires Python 3.6 or newer and nothing else.

### Options

| Command | Effect |
| --- | --- |
| `patch_hammer_anvil.py <file>` | Apply the fix (fallback after 90 s) |
| `patch_hammer_anvil.py <file> --delay 60` | Apply with a different fallback delay (10–600 s) |
| `patch_hammer_anvil.py <file> --check` | Report state, change nothing |
| `patch_hammer_anvil.py <file> --revert` | Undo, using `<file>.hammeranvil.undo` |

It also works directly on an extracted `RESOURCE.PAK`.

## What it changes

The mission is stored as a plain-text script (`mission\08_blockade.wrl`, inside
`RESOURCE.PAK`). After the Kethor's scripted spin ends, the script hands it to
the AI at whatever heading the spin left it:

```
ctrl+ kethorfm, kethor
kethorai.flyWPRoute wp15
```

In PCSX2 the AI then fails to turn the ship toward waypoint `wp15` (the ram
point), so it flies off. This matches the observation in the issue thread that
the ram works if the ship has finished turning before the last orbital gun is
destroyed. On real hardware the turn works.

The patch makes two changes to the mission script:

1. **Face fix.** Inserts `face kethor, wp15` just before the AI takes over, so
   the Kethor starts already pointing at the ram point.
2. **Fallback.** Adds a "Kethor rescue" event that, 90 seconds (configurable)
   after the hand-over, warps the Kethor onto `wp15` if it hasn't rammed yet.
   The ram sequence cancels this event, so it never fires after a normal ram.

This works around the problem rather than fixing the underlying emulation
difference, which is still unknown.

## Safety

- **Same size.** The edit does not change the file size. Extra whitespace in
  neighbouring script lines is tightened to pay for the added text, so no file
  offsets or disc sectors move.
- **Checksum guarded.** The patcher only edits a mission file whose SHA-256
  matches the original USA disc, and refuses anything else.
- **Reversible.** Applying writes a small undo file next to the image;
  `--revert` restores the original bytes exactly.

## Legal

This repository contains only a patcher script. It does not include any game
files and you must supply your own copy of the game. Please don't upload
patched images.

## Credits

Cause analysis and discussion by the reporters in
[PCSX2 issue #1927](https://github.com/PCSX2/pcsx2/issues/1927).
