#!/usr/bin/env python3
"""
Star Wars: Jedi Starfighter (PS2, USA SLUS-20293) - "Hammer and Anvil" Kethor fix.

Problem: in PCSX2 the Kethor often flies off into space instead of ramming the
shield projector, soft-locking Mission 7 (PCSX2 issue #1927).

The mission script ends the Kethor's scripted spin, then hands it to the AI
(`ctrl+ kethorfm, kethor` / `kethorai.flyWPRoute wp15`) at whatever heading the
spin left it. This patch makes two changes to that mission script:

  1. FACE FIX  - inserts `face kethor, wp15` just before the AI takes over, so it
                 starts already pointing at the ram point.
  2. FALLBACK  - adds an event that, DELAY seconds after the hand-over, warps the
                 Kethor onto wp15 (the ram point) if it hasn't rammed yet. The
                 ram sequence cancels this event, so it never fires after a
                 normal ram.

The edit is SAME SIZE (extra whitespace elsewhere in the mission script is
tightened to pay for the added text), so no file offsets or disc sectors move.
It works in place on RESOURCE.PAK or an uncompressed .iso/.bin of the USA disc.

Usage:
  patch_hammer_anvil.py <file>                 apply (fallback after 90 s)
  patch_hammer_anvil.py <file> --delay 60      apply with a different fallback delay (10-600 s)
  patch_hammer_anvil.py <file> --check         report state, change nothing
  patch_hammer_anvil.py <file> --revert        undo, using <file>.hammeranvil.undo
"""
import sys, os, re, json, hashlib

HEAD = b'LoadScene\r\n{\r\nfilename "08_Blockade.scene"'
ORIG_LEN = 124084
ORIG_SHA256 = '7595a960e3347fb471cc96a51985dfccda8d666afbb56c3300939f18a4c15f6b'

OLD1 = ('script        "StopMissionTimer kethortime"  "friends.addcraft kethor"  "friends.addcraft tritus"  '
        '"_simplemover.removeactor kethor"  "ctrl+ kethorfm, kethor"        "kethorai.setThrottle .3"  '
        '"kethorai.flyWPRoute wp15"  "DestroyEvent spin kethor"  "DestroyEvent spinning kethor"  '
        '"DestroyEvent keep spinning"  "DestroyEvent Back to beginning"  "set kethor.minhitpoints = 10"')
NEW1 = OLD1.replace('script        "', 'script  "', 1).replace(
        '"ctrl+ kethorfm, kethor"        "', '"face kethor, wp15"  "ctrl+ kethorfm, kethor"  "', 1)
OLD2 = 'script        "set kethor.minhitpoints = 0"'
NEW2 = 'script  "destroyevent Kethor rescue"  "set kethor.minhitpoints = 0"'
ANCHOR = 'name  "Kethor is back3"'          # new event goes after this event block
RESCUE = ('OnEventProxy {{\r\nexecutepercentage 100\r\nevent  "kethor is back"\r\ndelay {delay}\r\n'
          'numplayervalidity 0\r\nenabled TRUE\r\nexecuteinterval 1\r\nname  "Kethor rescue"\r\n'
          'actions  [ ScriptAction {{\r\nscript  "warp kethor, wp15"\r\n}}\r\n]\r\n}}\r\n')

def build(orig, delay):
    t = orig.decode('latin1')
    for s in (OLD1, OLD2, ANCHOR):
        if t.count(s) != 1: sys.exit('Unexpected mission script contents (%r).' % s[:40])
    i1, i2, ia = t.index(OLD1), t.index(OLD2), t.index(ANCHOR)
    close = '\r\n}\r\n]\r\n}\r\n'
    ins = t.index(close, ia) + len(close)
    assert i1 < i2 < ia < ins
    new = (t[:i1] + NEW1 + t[i1+len(OLD1):i2] + NEW2 + t[i2+len(OLD2):ins]
           + RESCUE.format(delay=delay) + t[ins:])
    need = len(new) - len(t)
    # Pay for the added text by tightening wide gaps between script strings after the edit.
    pos = ins + len(RESCUE.format(delay=delay)) - 0
    head, tail = new[:pos], new[pos:]
    out, saved, p = [], 0, 0
    lines = tail.split('\r\n')
    for li, line in enumerate(lines):
        if saved < need and line.startswith('script'):
            pieces, last = [], 0
            for m in re.finditer(r'"[^"]*"', line):
                gap = line[last:m.start()]
                if saved < need and len(gap) > 2 and last > 0 or (last == 0 and len(gap) > len('script') + 2):
                    base = 0 if last > 0 else len('script')
                    cut = min(len(gap) - base - 2, need - saved)
                    if cut > 0: gap = gap[:len(gap)-cut]; saved += cut
                pieces.append(gap); pieces.append(m.group(0)); last = m.end()
            line = ''.join(pieces) + line[last:]
        out.append(line)
        if saved >= need:
            out.extend(lines[li+1:]); break
    if saved < need: sys.exit('Not enough spare whitespace to keep the file size unchanged.')
    final = head + '\r\n'.join(out)
    assert len(final) == len(t), (len(final), len(t))
    b = final.encode('latin1')
    # changed span [i1, end)
    end = len(b)
    while b[end-1] == orig[end-1]: end -= 1
    return b, i1, end

def find_live(data):
    offs, i = [], data.find(HEAD)
    while i != -1:
        if hashlib.sha256(data[i:i+ORIG_LEN]).hexdigest() == ORIG_SHA256: offs.append(('orig', i))
        i = data.find(HEAD, i + 1)
    return offs

def main():
    if len(sys.argv) < 2 or sys.argv[1].startswith('-'): print(__doc__); sys.exit(1)
    path, args = sys.argv[1], sys.argv[2:]
    delay = 90
    if '--delay' in args:
        delay = int(args[args.index('--delay') + 1])
        if not 10 <= delay <= 600: sys.exit('--delay must be 10-600 seconds')
    undo = path + '.hammeranvil.undo'
    data = open(path, 'rb').read()
    live = find_live(data)
    patched = [i for i in range(0) ]
    if '--check' in args:
        print('Unpatched mission found at:', [hex(o) for _, o in live] or 'none',
              '| undo file present:', os.path.exists(undo)); return
    if '--revert' in args:
        if not os.path.exists(undo): sys.exit('No undo file found next to the image.')
        u = json.load(open(undo)); off = u['offset']; old = bytes.fromhex(u['original'])
        cur = data[off:off+len(old)]
        if hashlib.sha256(cur).hexdigest() != u['patched_sha256']: sys.exit('Image differs from the patched state; not reverting.')
        with open(path, 'r+b') as f: f.seek(off); f.write(old)
        os.remove(undo); print('Reverted at offset', hex(off)); return
    if os.path.exists(undo): sys.exit('Already patched (undo file exists). Use --revert first to change the delay.')
    if len(live) != 1:
        sys.exit('Could not find exactly one unpatched Hammer and Anvil mission (found %d). Wrong file, already patched, '
                 'or compressed image (CSO/CHD) - use an uncompressed ISO of the USA disc.' % len(live))
    base = live[0][1]
    orig = data[base:base+ORIG_LEN]
    b, a, e = build(orig, delay)
    seg_old, seg_new = orig[a:e], b[a:e]
    with open(path, 'r+b') as f: f.seek(base + a); f.write(seg_new)
    json.dump({'offset': base + a, 'original': seg_old.hex(),
               'patched_sha256': hashlib.sha256(seg_new).hexdigest(), 'delay': delay}, open(undo, 'w'))
    print('Patched mission script at', hex(base + a), '- %d bytes changed, file size unchanged, fallback delay %ds.' % (e - a, delay))
    print('Undo info saved to', undo)

main()
