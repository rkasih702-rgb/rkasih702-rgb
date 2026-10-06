#!/usr/bin/env python3
"""
Generate an animated 3D (isometric) GitHub contribution card:
  - isometric contribution bars
  - animated circuit traces around the avatar
  - language donut chart

Usage:
  python generate_motd.py --user rkasih702-rgb --out motd.svg        # real data (needs GITHUB_TOKEN)
  python generate_motd.py --user rkasih702-rgb --out motd.svg --demo # sample data, no network
  python generate_motd.py --user rkasih702-rgb --photo avatar.png    # use your own photo

Only the Python standard library is used.
"""
import argparse, base64, datetime as dt, json, math, os, random, sys, urllib.request

W, H = 880, 390
X0, Y0 = 115.0, 346.25          # origin of the isometric grid
DX, DY = 12.125, 3.75           # half-width / half-height of one tile
HEIGHT = {0: 1, 1: 8, 2: 18, 3: 20.5, 4: 23}
COLORS = {  # right face, left face, top face
    0: ("#0d1117", "#11151a", "#161b22"),
    1: ("#072a19", "#0a3520", "#0e4429"),
    2: ("#004620", "#005828", "#006d32"),
    3: ("#186b2b", "#1e8535", "#26a641"),
    4: ("#258836", "#2eaa43", "#39d353"),
}
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif'


# ----------------------------------------------------------------- data ----
def gql(query, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": "bearer " + token, "Content-Type": "application/json",
                 "User-Agent": "motd-generator"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_real(user, token):
    q = """{ user(login: "%s") {
      contributionsCollection { contributionCalendar { totalContributions
        weeks { contributionDays { date contributionCount weekday } } } }
      repositories(first: 100, ownerAffiliations: OWNER, isFork: false) { nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } } } } } } }""" % user
    u = gql(q, token)["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    cells = []
    for w, week in enumerate(cal["weeks"]):
        for day in week["contributionDays"]:
            cells.append((w, day["weekday"], day["date"], day["contributionCount"]))
    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]
            name, color = n["name"], n["color"] or "#484f58"
            langs[name] = (langs.get(name, (0, color))[0] + e["size"], color)
    ranked = sorted(((s, n, c) for n, (s, c) in langs.items()), reverse=True)
    total = sum(s for s, _, _ in ranked) or 1
    languages = [(n, c, s * 100.0 / total) for s, n, c in ranked]
    return cells, cal["totalContributions"], languages


def fetch_demo():
    rnd = random.Random(702)
    today = dt.date.today()
    last_sunday = today - dt.timedelta(days=(today.weekday() + 1) % 7)
    start = last_sunday - dt.timedelta(weeks=52)
    cells, d = [], start
    while d <= today:
        w, wd = (d - start).days // 7, (d.weekday() + 1) % 7
        c = rnd.choice([1, 1, 2, 3, 4, 5, 8]) if rnd.random() < 0.28 else 0
        cells.append((w, wd, d.isoformat(), c))
        d += dt.timedelta(days=1)
    langs = [("Vue", "#41b883", 38.0), ("JavaScript", "#f1e05a", 22.0),
             ("Python", "#3572A5", 18.0), ("CSS", "#563d7c", 12.0), ("HTML", "#e34c26", 10.0)]
    return cells, sum(c[3] for c in cells), langs


def fetch_photo(user, path):
    try:
        if path:
            raw = open(path, "rb").read()
        else:
            req = urllib.request.Request("https://github.com/%s.png?size=400" % user,
                                         headers={"User-Agent": "motd-generator"})
            raw = urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        print("note: no photo embedded (%s)" % e, file=sys.stderr)
        return None
    mime = "image/png" if raw[:4] == b"\x89PNG" else "image/jpeg"
    return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode())


# --------------------------------------------------------------- pieces ----
def levels(cells):
    nz = sorted(c[3] for c in cells if c[3] > 0)
    if not nz:
        return lambda c: 0
    t1, t2, t3 = nz[len(nz) // 4], nz[len(nz) // 2], nz[(3 * len(nz)) // 4]
    return lambda c: 0 if c <= 0 else min(4, 1 + (c > t1) + (c > t2) + (c > t3))


def bar(w, d, count, date, lvl):
    cx, base = X0 + DX * (w - d), Y0 - DY * (w + d)
    h = HEIGHT[lvl]
    cy = base - h
    right, left, top = COLORS[lvl]
    f = lambda pts: " ".join("%.2f,%.2f" % p for p in pts)
    pr = [(cx, cy + DY), (cx + DX, cy), (cx + DX, cy + h), (cx, cy + DY + h)]
    pl = [(cx - DX, cy), (cx, cy + DY), (cx, cy + DY + h), (cx - DX, cy + h)]
    pt = [(cx, cy - DY), (cx + DX, cy), (cx, cy + DY), (cx - DX, cy)]
    rise = 0.015 * (w + 6 - d)
    wave = 1.0 + 0.04 * (w + 6 - d)
    label = "%d contribution%s on %s" % (count, "" if count == 1 else "s", date)
    st = 'stroke="#0d1117" stroke-width="0.5"'
    return ('<g class="bar-group" style="animation-delay: %.3fs, %.3fs;"><title>%s</title>'
            '<polygon points="%s" fill="%s" %s/><polygon points="%s" fill="%s" %s/>'
            '<polygon points="%s" fill="%s" %s/></g>'
            % (rise, wave, label, f(pr), right, st, f(pl), left, st, f(pt), top, st))


def bezier_len(p0, p1, p2, p3, n=40):
    total, prev = 0.0, p0
    for i in range(1, n + 1):
        t = i / n
        x = (1-t)**3*p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t*t*p2[0] + t**3*p3[0]
        y = (1-t)**3*p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t*t*p2[1] + t**3*p3[1]
        total += math.hypot(x - prev[0], y - prev[1])
        prev = (x, y)
    return total


def traces(n=24, seed=11):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        side = rnd.choice("LLRRTT")
        if side == "L":
            s, e = (247.0, rnd.uniform(60, 330)), (-5.0, rnd.uniform(110, 340))
        elif side == "R":
            s, e = (633.0, rnd.uniform(80, 165)), (885.0, rnd.uniform(130, 370))
        else:
            sx = rnd.uniform(247, 545)
            s, e = (sx, 2.0), (min(540, max(170, sx + rnd.uniform(-150, 150))), -5.0)
        c1 = (s[0] + (e[0]-s[0])*0.3, s[1] + (e[1]-s[1])*0.35 + rnd.uniform(-40, 40))
        c2 = (s[0] + (e[0]-s[0])*0.75, e[1] + rnd.uniform(-40, 40))
        ln = bezier_len(s, c1, c2, e)
        d = "M %.1f %.1f C %.1f %.1f, %.1f %.1f, %.1f %.1f" % (s + c1 + c2 + e)
        wb = rnd.uniform(1.2, 1.7)
        dur, begin = round(4 + ln / 80, 1), round(0.9 * i, 1)
        anim = ('<animate attributeName="stroke-dashoffset" values="%.1f;%.1f;%.1f" keyTimes="0;0.7;1" '
                'calcMode="spline" keySplines="0.4 0 0.6 1;0 0 1 1" dur="%.1fs" begin="%.1fs" '
                'repeatCount="indefinite"/>' % (ln, -0.74 * ln, ln, dur, begin))
        g = ['<path id="tr%d" d="%s" fill="none" stroke="none"/>' % (i, d),
             '<path d="%s" fill="none" stroke="#52525b" stroke-width="%.1f" stroke-linecap="round" opacity="0.55"/>' % (d, wb)]
        for color, width, frac, op in (("#a1a1aa", wb + 1.7, 0.26, 0.25), ("#e4e4e7", wb + 0.5, 0.15, 0.5),
                                       ("#f4f4f5", 0.5, 0.06, 0.8)):
            g.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" '
                     'stroke-dasharray="%.1f %.1f" stroke-dashoffset="%.1f" opacity="%s">%s</path>'
                     % (d, color, width, frac * ln, ln, ln, op, anim))
        g.append('<circle r="2.5" fill="#ffffff" opacity="0"><animateMotion dur="%.1fs" begin="%.1fs" '
                 'repeatCount="indefinite" keyPoints="0;1;1" keyTimes="0;0.7;1" calcMode="spline" '
                 'keySplines="0.4 0 0.6 1;0 0 1 1"><mpath href="#tr%d"/></animateMotion>'
                 '<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.02;0.68;0.7;1" '
                 'dur="%.1fs" begin="%.1fs" repeatCount="indefinite"/></circle>' % (dur, begin, i, dur, begin))
        out.append("\n".join(g))
    return "\n".join(out)


def donut(languages, demo):
    top = languages[:5]
    rest = sum(p for _, _, p in languages[5:])
    if rest > 0.05:
        top = top + [("Other", "#484f58", rest)]
    C = 2 * math.pi * 42
    cx, cy = 810, 255
    parts = ['<g class="lang-chart"><circle cx="%d" cy="%d" r="42" fill="none" stroke="#161b22" stroke-width="14"/>' % (cx, cy)]
    off = 0.0
    for i, (name, color, pct) in enumerate(top):
        seg = C * pct / 100.0
        parts.append('<circle class="lang-seg" cx="%d" cy="%d" r="42" fill="none" stroke="%s" stroke-width="12" '
                     'stroke-dasharray="%.2f %.2f" stroke-dashoffset="%.2f" style="animation-delay: %.2fs;">'
                     '<title>%s (%.1f%%)</title></circle>' % (cx, cy, color, seg, C - seg, -off, 0.8 + 0.15 * i, name, pct))
        off += seg
    ff = 'font-family="%s"' % FONT.replace('"', "'")
    parts.append('<text x="%d" y="252" text-anchor="middle" fill="#c9d1d9" %s font-size="10" font-weight="600">Languages</text>' % (cx, ff))
    parts.append('<text x="%d" y="265" text-anchor="middle" fill="#8b949e" %s font-size="8">%d used</text>' % (cx, ff, len(languages)))
    for i, (name, color, pct) in enumerate(top[:5]):
        y = 314 + 13 * i
        parts.append('<rect x="766" y="%d" width="6" height="6" rx="1" fill="%s"/>' % (y, color))
        parts.append('<text x="776" y="%d" fill="#8b949e" %s font-size="8">%s %d%%</text>' % (y + 5, ff, name, round(pct)))
    parts.append("</g>")
    return "\n".join(parts)


def month_labels(cells):
    first_of_week, labels = {}, []
    for w, d, date, _ in cells:
        if date.endswith("-01"):
            first_of_week[w] = int(date[5:7])
    first = cells[0]
    start_month = int(first[2][5:7])
    ws = sorted(first_of_week)
    if not ws or ws[0] > 1:
        first_of_week[0] = start_month
    for w in sorted(first_of_week):
        x, y = X0 + DX * w, 330 - DY * w
        labels.append('<text class="label" x="%.2f" y="%.2f" text-anchor="middle">%s</text>' % (x, y, MONTHS[first_of_week[w] - 1]))
    for d, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        x, y = 76.81 - DX * (d - 1), 347.38 - DY * (d - 1)
        labels.append('<text class="label" x="%.2f" y="%.2f" text-anchor="end">%s</text>' % (x, y, name))
    return "\n".join(labels)


# ------------------------------------------------------------- assemble ----
def build(user, cells, total, languages, photo, demo):
    lv = levels(cells)
    bars = [bar(w, d, c, date, lv(c)) for w, d, date, c in sorted(cells, key=lambda t: (-(t[0] + t[1]), t[0]))]
    if photo:
        center = ('<g opacity="0.5" mask="url(#photo-mask)"><image x="245" y="0" width="390" height="390" '
                  'preserveAspectRatio="xMidYMid slice" href="%s"/></g>' % photo)
    else:
        center = '<rect x="245" y="0" width="390" height="390" fill="url(#glow-fill)" opacity="0.6"/>'
    badge = ('<text class="label" x="20" y="376" fill="#f85149" style="fill:#f85149">sample data - run with a GitHub token for real stats</text>'
             if demo else "")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs>
<filter id="glow-strong" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="clip-outside-char"><path clip-rule="evenodd" d="M 0 0 L {W} 0 L {W} {H} L 0 {H} Z M 245 0 L 635 0 L 635 {H} L 245 {H} Z"/></clipPath>
<radialGradient id="photo-fade" cx="50%" cy="50%" r="62%"><stop offset="55%" stop-color="#fff"/><stop offset="100%" stop-color="#000"/></radialGradient>
<radialGradient id="glow-fill" cx="50%" cy="50%" r="55%"><stop offset="0%" stop-color="#30363d"/><stop offset="100%" stop-color="#0d1117" stop-opacity="0"/></radialGradient>
<mask id="photo-mask"><rect x="245" y="0" width="390" height="390" fill="url(#photo-fade)"/></mask>
<style>
.bg{{fill:#0d1117}}
.bar-group{{opacity:0;animation:rise .6s cubic-bezier(.34,1.56,.64,1) forwards,wave 4s ease-in-out infinite}}
@keyframes rise{{from{{opacity:0;transform:translateY(18px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes wave{{0%,100%{{transform:translateY(0);opacity:1}}8%{{transform:translateY(-5px);opacity:.75}}16%{{transform:translateY(0);opacity:1}}22%{{transform:translateY(-3px);opacity:.85}}30%{{transform:translateY(0);opacity:1}}}}
.lang-seg{{transform:rotate(-90deg);transform-origin:810px 255px;opacity:0;animation:seg-draw .7s cubic-bezier(.25,.46,.45,.94) forwards}}
@keyframes seg-draw{{from{{stroke-dasharray:0 9999;opacity:.5}}to{{opacity:1}}}}
.circuit-traces{{clip-path:url(#clip-outside-char)}}
.label{{fill:#8b949e;font-family:{FONT};font-size:10px}}
.title{{fill:#c9d1d9;font-family:{FONT};font-size:14px;font-weight:600}}
.subtitle{{fill:#8b949e;font-family:{FONT};font-size:11px}}
</style>
</defs>
<rect class="bg" width="{W}" height="{H}" rx="6"/>
{center}
<g class="circuit-traces">
{traces()}
</g>
<text class="title" x="20" y="28">{total} contributions in the last year</text>
<text class="subtitle" x="20" y="46">@{user}</text>
{month_labels(cells)}
{chr(10).join(bars)}
{donut(languages, demo)}
{badge}
</svg>
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="rkasih702-rgb")
    ap.add_argument("--out", default="motd.svg")
    ap.add_argument("--photo", help="path to a photo (png/jpg); default = your GitHub avatar")
    ap.add_argument("--demo", action="store_true", help="use sample data (no token needed)")
    a = ap.parse_args()

    if a.demo:
        cells, total, langs = fetch_demo()
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            sys.exit("Set GITHUB_TOKEN (or GH_TOKEN), or use --demo")
        cells, total, langs = fetch_real(a.user, token)
    if not langs:
        langs = [("No code yet", "#484f58", 100.0)]
    svg = build(a.user, cells, total, langs, fetch_photo(a.user, a.photo), a.demo)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", a.out, "-", total, "contributions,", len(cells), "days")


if __name__ == "__main__":
    main()
