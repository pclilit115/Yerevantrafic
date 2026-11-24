"""Build compact network for the Yerevan 3D traffic sim.
Inputs: data/roads.json, data/corridor.json, data/kml.json
Output: out/net.json
"""
import json, math, heapq, collections, re

R = json.load(open('data4/roads.json'))
COR = json.load(open('data/corridor.json'))
K = json.load(open('data/kml.json'))

coords = R['coords']
nodes = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
key = {p: i for i, p in enumerate(nodes)}
ways = [[t, n] for t, n in R['ways']]
_seen = set(tuple(nodes[i] for i in n) for t, n in ways)
COR = COR + json.load(open('data/corridor2.json')) + json.load(open('data/corridor3.json'))
for t, pts in COR:
    _k = tuple(map(tuple, pts))
    if _k in _seen: continue
    _seen.add(_k)
    idx = []
    for p in pts:
        p = (p[0], p[1])
        if p not in key:
            key[p] = len(nodes); nodes.append(p)
        idx.append(key[p])
    ways.append([t, idx])

CLS = {'motorway': 0, 'trunk': 0, 'primary': 1, 'secondary': 2, 'tertiary': 3,
       'motorway_link': 4, 'trunk_link': 4, 'primary_link': 4, 'secondary_link': 4, 'tertiary_link': 4,
       'unclassified': 5, 'residential': 5, 'living_street': 6}
DEF_ONE = {0: 3, 1: 3, 2: 2, 3: 2, 4: 1, 5: 1, 6: 1}
DEF_TWO = {0: 2, 1: 2, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1}
SPD = {0: 60, 1: 60, 2: 50, 3: 40, 4: 40, 5: 30, 6: 20}

names = []; name_ix = {}
def nm(t):
    n = t.get('name') or ''
    if not n: return -1
    if n not in name_ix:
        name_ix[n] = len(names); names.append(n)
    return name_ix[n]

def toint(s, d):
    try: return max(1, int(float(str(s).split(';')[0])))
    except Exception: return d

use = collections.Counter()
for t, n in ways:
    for i, x in enumerate(n):
        use[x] += 1 if 0 < i < len(n) - 1 else 2

edges = []  # [a,b,pts,cls,name,lF,lB,spd,layer,round]
for t, n in ways:
    h = t['highway']; c = CLS.get(h)
    if c is None or len(n) < 2: continue
    ow = t.get('oneway'); rnd = t.get('junction') in ('roundabout', 'circular')
    rev = ow == '-1'
    oneway = ow in ('yes', '1', 'true', '-1') or rnd or h in ('motorway', 'motorway_link')
    lanes = t.get('lanes')
    if oneway:
        lF = toint(lanes, DEF_ONE[c]); lB = 0
    else:
        if lanes:
            L = toint(lanes, 2)
            lF = toint(t.get('lanes:forward'), 0) if t.get('lanes:forward') else 0
            lB = toint(t.get('lanes:backward'), 0) if t.get('lanes:backward') else 0
            if not lF and not lB: lF = max(1, (L + 1) // 2); lB = max(1, L // 2)
            elif not lB: lB = max(1, L - lF)
            elif not lF: lF = max(1, L - lB)
        else:
            lF = lB = DEF_TWO[c]
    lF, lB = min(lF, 5), min(lB, 5)
    if rev: n = n[::-1]
    spd = toint(t.get('maxspeed'), SPD[c]) if t.get('maxspeed') else SPD[c]
    layer = 1 if t.get('bridge') else (-1 if t.get('tunnel') else 0)
    # split at shared nodes
    cur = [n[0]]
    for x in n[1:]:
        cur.append(x)
        if use[x] >= 2 and x != n[-1]:
            edges.append([cur[0], cur[-1], cur, c, nm(t), lF, lB, spd, layer, int(rnd)]); cur = [x]
    if len(cur) >= 2:
        edges.append([cur[0], cur[-1], cur, c, nm(t), lF, lB, spd, layer, int(rnd)])

# drop degenerate (zero length)
def plen(pts):
    return sum(math.dist(nodes[pts[i]], nodes[pts[i + 1]]) for i in range(len(pts) - 1))
edges = [e for e in edges if plen(e[2]) > 0.5]
print('nodes', len(nodes), 'edges', len(edges))

# directed links
links = []  # (edge, dir)
for ei, e in enumerate(edges):
    links.append((ei, 0))
    if e[6] > 0: links.append((ei, 1))
lid = {l: i for i, l in enumerate(links)}
def lpts(l):
    e = edges[l[0]]; return e[2] if l[1] == 0 else e[2][::-1]
def lstart(l): return lpts(l)[0]
def lend(l): return lpts(l)[-1]
def llen(l): return plen(edges[l[0]][2])
out_of = collections.defaultdict(list)
for i, l in enumerate(links): out_of[lstart(l)].append(i)

# ---------- geometry helpers ----------
def seg_d(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L = dx * dx + dy * dy or 1
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy), t
def poly_proj(p, poly):
    """distance to polyline, arc position, segment heading"""
    best = (1e18, 0, 0); acc = 0
    for i in range(len(poly) - 1):
        a, b = poly[i], poly[i + 1]; L = math.dist(a, b)
        d, t = seg_d(p, a, b)
        if d < best[0]: best = (d, acc + t * L, math.atan2(b[1] - a[1], b[0] - a[0]))
        acc += L
    return best
def samples(l, step=12):
    pts = [nodes[i] for i in lpts(l)]; out = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]; L = math.dist(a, b); k = max(1, int(L / step))
        for j in range(k):
            t = (j + .5) / k; out.append(((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), math.atan2(b[1] - a[1], b[0] - a[0])))
    return out
def angdiff(a, b):
    d = (a - b + math.pi) % (2 * math.pi) - math.pi; return abs(d)

# spatial grid of links
G = collections.defaultdict(set); GS = 80
for i, l in enumerate(links):
    for (p, h) in samples(l, 30):
        G[(int(p[0] // GS), int(p[1] // GS))].add(i)
def links_near_poly(poly, rad=80):
    s = set()
    for i in range(len(poly) - 1):
        a, b = poly[i], poly[i + 1]; L = math.dist(a, b); k = max(1, int(L / 40))
        for j in range(k + 1):
            t = j / k; x = a[0] + (b[0] - a[0]) * t; y = a[1] + (b[1] - a[1]) * t
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1): s |= G.get((int(x // GS) + dx, int(y // GS) + dy), set())
    return s

def match_route(poly):
    """map-match a polyline to directed links over the full graph with a distance penalty"""
    cand = links_near_poly(poly)
    cost = {}
    for i in range(len(links)):
        l = links[i]; L = llen(l)
        if i not in cand: cost[i] = L * 60 + 500; continue
        sm = samples(l, 10); tot = 0
        for p, h in sm:
            d, s, hh = poly_proj(p, poly)
            tot += min(60, (d / 12) ** 2) + (4 if angdiff(h, hh) > 1.9 else 0)
        cost[i] = L * (1 + tot / max(1, len(sm))) + 3
    def nearest(p, start, k=8):
        c = {}
        for i in cand:
            n = lstart(links[i]) if start else lend(links[i])
            c[n] = math.dist(nodes[n], p)
        return sorted(c, key=c.get)[:k]
    def dij(s, t):
        dist = {s: 0}; prev = {}; pq = [(0, s)]
        while pq:
            d, n = heapq.heappop(pq)
            if n == t: break
            if d > dist.get(n, 1e18): continue
            for i in out_of[n]:
                m = lend(links[i]); nd = d + cost[i]
                if nd < dist.get(m, 1e18): dist[m] = nd; prev[m] = i; heapq.heappush(pq, (nd, m))
        if t not in prev: return None
        path = []; n = t
        while n != s:
            i = prev[n]; path.append(i); n = lstart(links[i])
        return path[::-1]
    path = None
    for s in nearest(poly[0], True):
        for t in nearest(poly[-1], False, 4):
            path = dij(s, t)
            if path: break
        if path: break
    if not path: return None
    off = [i for i in path if i not in cand]
    if off: print('   off-corridor links', len(off), round(sum(llen(links[i]) for i in off)), 'm')
    return path


def sub_poly(poly, a, b):
    """polyline portion between arc a and b"""
    out = []; acc = 0
    for i in range(len(poly) - 1):
        p, q = poly[i], poly[i + 1]; L = math.dist(p, q)
        if L == 0: continue
        for t in (0, 1):
            pass
        s0, s1 = acc, acc + L
        if s1 >= a and s0 <= b:
            ta = max(0, (a - s0) / L); tb = min(1, (b - s0) / L)
            pa = (p[0] + (q[0] - p[0]) * ta, p[1] + (q[1] - p[1]) * ta)
            pb = (p[0] + (q[0] - p[0]) * tb, p[1] + (q[1] - p[1]) * tb)
            if not out: out.append(pa)
            out.append(pb)
        acc = s1
    return out

def match_route_seg(poly, step=7000):
    total = sum(math.dist(poly[i], poly[i + 1]) for i in range(len(poly) - 1))
    marks = [0]
    while marks[-1] + step < total - step * .4: marks.append(marks[-1] + step)
    marks.append(total)
    path = []; cur = None
    for k in range(len(marks) - 1):
        a, b = marks[k], marks[k + 1]
        sp = sub_poly(poly, max(0, a - 60), min(total, b + 60))
        if len(sp) < 2: continue
        tgt = sub_poly(poly, b - 1, b)[-1] if b > 1 else poly[-1]
        cand = links_near_poly(sp)
        cost = {}
        for i in cand:
            l = links[i]; sm = samples(l, 10); tot = 0
            for p, h in sm:
                d, s_, hh = poly_proj(p, sp)
                tot += min(60, (d / 12) ** 2) + (25 if angdiff(h, hh) > 1.9 else 0)
            cost[i] = llen(l) * (1 + tot / max(1, len(sm))) + 3
        def c(i): return cost.get(i, llen(links[i]) * 60 + 500)
        if cur is None:
            starts = sorted({lstart(links[i]) for i in cand}, key=lambda n: math.dist(nodes[n], sp[0]))[:6]
        else: starts = [cur]
        tp = sub_poly(poly, max(0, b - 25), b); th = math.atan2(tp[-1][1] - tp[0][1], tp[-1][0] - tp[0][0]) if len(tp) > 1 else 0
        def endh(i):
            p = lpts(links[i]); a_, b_ = nodes[p[-2]], nodes[p[-1]]; return math.atan2(b_[1] - a_[1], b_[0] - a_[0])
        good = [i for i in cand if math.dist(nodes[lend(links[i])], tgt) < 60 and angdiff(endh(i), th) < 0.9]
        ends = sorted({lend(links[i]) for i in good}, key=lambda n: math.dist(nodes[n], tgt))[:6] or sorted({lend(links[i]) for i in cand}, key=lambda n: math.dist(nodes[n], tgt))[:4]
        best = None
        for s0 in starts:
            dist = {s0: 0}; prev = {}; pq = [(0, s0)]; endset = set(ends); found = None
            while pq:
                d, n = heapq.heappop(pq)
                if n in endset and n != s0: found = n; break
                if d > dist.get(n, 1e18): continue
                if d > 4e5: break
                for i in out_of[n]:
                    m = lend(links[i]); nd = d + c(i)
                    if nd < dist.get(m, 1e18): dist[m] = nd; prev[m] = i; heapq.heappush(pq, (nd, m))
            if found is not None:
                seg = []; n = found
                while n != s0:
                    i = prev[n]; seg.append(i); n = lstart(links[i])
                best = seg[::-1]; break
        if best is None:
            print('   segment fail at', round(a)); continue
        path += best; cur = lend(links[best[-1]])
    return path

lines = K['lines']
existing = [l for l in lines if l['color'] == 'ff54c93c']
impossible = [l for l in lines if l['color'] == 'ff444444']
routes = [l for l in lines if l['color'] in ('ff8136b6', 'ff3360fb', 'ff00ccff')]
RCOL = {'ff8136b6': '#b63681', 'ff3360fb': '#fb6033', 'ff00ccff': '#ffcc00'}

def frac_near(l, poly, rad, need_dir=False):
    sm = samples(l, 8); c = 0
    for p, h in sm:
        d, s, hh = poly_proj(p, poly)
        if d < rad and (not need_dir or angdiff(h, hh) < 0.8): c += 1
    return c / max(1, len(sm))

# existing bus lanes (both directions, they're drawn as back-and-forth sketches)
bus_today = set()
for ex in existing:
    for i in links_near_poly(ex['pts'], 40):
        l = links[i]; e = edges[l[0]]
        nl = e[5] if l[1] == 0 else e[6]
        if e[3] <= 3 and frac_near(l, ex['pts'], 16) > 0.6 and nl >= 2: bus_today.add(i)
print('today bus links', len(bus_today))

# impossible: links that overlap impossible segments
imp_links = set()
for im in impossible:
    for i in links_near_poly(im['pts'], 40):
        if frac_near(links[i], im['pts'], 18) > 0.5: imp_links.add(i)

route_out = []; bus_prop = set(bus_today)
for r in routes:
    head = r['name'].split('\n')[0].strip()
    rr = {'name': head, 'desc': r['desc'], 'color': RCOL[r['color']], 'meta': ' '.join(r['name'].split('\n')[1:]).strip(), 'dirs': []}
    for dname, poly in (('A→B', r['pts']), ('B→A', r['pts'][::-1])):
        path = match_route_seg(poly)
        if not path: print('NO MATCH', head, dname); continue
        L = sum(llen(links[i]) for i in path)
        print(head[:40], dname, len(path), 'links', round(L / 1000, 2), 'km')
        for i in path:
            l = links[i]; e = edges[l[0]]; nl = e[5] if l[1] == 0 else e[6]
            if nl >= 2 and i not in imp_links and e[3] <= 4: bus_prop.add(i)
        rr['dirs'].append({'d': dname, 'path': path, 'len': round(L)})
    route_out.append(rr)
print('proposal bus links', len(bus_prop), 'impossible', len(imp_links))

# stops: directional points
stops = []
for p in K['points']:
    n = p['name']
    m = re.search(r'\((A|B)-&?g?t?;?>?(B|A)\)', n) or re.search(r'\((A|B)->(B|A)\)', n)
    if not m: continue
    d = 'A→B' if m.group(1) == 'A' else 'B→A'
    clean = re.sub(r'\s*\((A|B)->(B|A)\)', '', n).strip()
    kind = 'new' if p['color'] == 'ff312ce3' else 'exist'
    hits = []
    for ri, r in enumerate(route_out):
        for di, dd in enumerate(r['dirs']):
            if dd['d'] != d: continue
            # position along path
            acc = 0; best = None
            for i in dd['path']:
                pts = [nodes[x] for x in lpts(links[i])]
                dd2, s, h = poly_proj(p['p'], pts)
                if best is None or dd2 < best[0]: best = (dd2, acc + s)
                acc += llen(links[i])
            if best and best[0] < 40: hits.append([ri, di, round(best[1])])
    stops.append({'n': clean, 'k': kind, 'p': [round(p['p'][0]), round(p['p'][1])], 'on': hits})
print('stops', len(stops), 'on routes', sum(1 for s in stops if s['on']))
labels = [{'n': p['name'], 'p': [round(p['p'][0]), round(p['p'][1])], 'c': p['color']} for p in K['points']
          if '->' not in p['name']]

# ---------- signals ----------
# major intersections: nodes with >=3 incident edges, >=2 of class<=3 ; cluster within 28 m
inc = collections.defaultdict(list)
for ei, e in enumerate(edges):
    inc[e[0]].append(ei); inc[e[1]].append(ei)
cand = [n for n, es in inc.items() if len(es) >= 3 and sum(1 for ei in es if edges[ei][3] <= 3) >= 2
        and not all(edges[ei][9] for ei in es if edges[ei][3] <= 3)]
cand_set = set(cand)
# union-find clustering
par = {n: n for n in cand}
def f(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
CG = collections.defaultdict(list)
for n in cand: CG[(int(nodes[n][0] // 30), int(nodes[n][1] // 30))].append(n)
for n in cand:
    gx, gy = int(nodes[n][0] // 30), int(nodes[n][1] // 30)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for m in CG.get((gx + dx, gy + dy), []):
                if m != n and math.dist(nodes[n], nodes[m]) < 30: par[f(n)] = f(m)
clusters = collections.defaultdict(list)
for n in cand: clusters[f(n)].append(n)
signals = []; link_sig = {}
for root, ns in clusters.items():
    nset = set(ns)
    # skip roundabout-only clusters
    inlinks = []
    for n in ns:
        for i, l in enumerate([]): pass
    for n in ns:
        for ei in inc[n]:
            e = edges[ei]
            for d in (0, 1):
                if d == 1 and e[6] == 0: continue
                l = (ei, d); i = lid.get(l)
                if i is None: continue
                if lend(l) == n and lstart(l) not in nset and not e[9]:
                    inlinks.append(i)
    if len(inlinks) < 2: continue
    # heading of approach (last segment)
    def head(i):
        p = lpts(links[i]); a, b = nodes[p[-2]], nodes[p[-1]]; return math.atan2(b[1] - a[1], b[0] - a[0])
    best = max(inlinks, key=lambda i: (-edges[links[i][0]][3], llen(links[i])))
    ax = head(best)
    ph = {}
    for i in inlinks:
        dd = angdiff(head(i), ax); dd = min(dd, math.pi - dd)
        ph[i] = 0 if dd < math.pi / 4 else 1
    if len(set(ph.values())) < 2:
        continue
    cx = sum(nodes[n][0] for n in ns) / len(ns); cy = sum(nodes[n][1] for n in ns) / len(ns)
    major = min(edges[links[i][0]][3] for i in inlinks)
    sid = len(signals)
    signals.append({'c': [round(cx), round(cy)], 'cyc': 100 if major <= 1 else 80, 'off': (sid * 37) % 100})
    for i, p in ph.items(): link_sig[i] = [sid, p]
print('signals', len(signals))

# ---------- output ----------
nodeset = set()
for e in edges: nodeset.update(e[2])
remap = {}; flat = []
for n in sorted(nodeset):
    remap[n] = len(flat) // 2; flat += [nodes[n][0], nodes[n][1]]
E = []
for e in edges:
    E.append([[remap[x] for x in e[2]], e[3], e[4], e[5], e[6], e[7], e[8], e[9]])
L = [[l[0], l[1]] for l in links]
out = {
    'nodes': flat, 'edges': E, 'names': names, 'links': L,
    'busToday': sorted(bus_today), 'busProp': sorted(bus_prop), 'imp': sorted(imp_links),
    'sig': signals, 'lsig': {str(k): v for k, v in link_sig.items()},
    'routes': route_out, 'stops': stops, 'labels': labels,
    'districts': R['districts'],
    'kml': [{'n': l['name'].split('\n')[0], 'd': l['desc'], 'c': l['color'], 'p': [[round(a), round(b)] for a, b in l['pts']]} for l in lines],
}
import os
os.makedirs('out', exist_ok=True)
json.dump(out, open('out/net.json', 'w'), ensure_ascii=False, separators=(',', ':'))
print('net.json', os.path.getsize('out/net.json'))
