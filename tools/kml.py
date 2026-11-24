import re,math,json
s=open('/mnt/user-data/uploads/40373e5c-map_data.kml',encoding='utf8').read()
L0,P0=44.50,40.18;KX=math.cos(math.radians(P0))*111320;KY=110540
prj=lambda lo,la:[round((lo-L0)*KX,1),round(-(la-P0)*KY,1)]
out={'lines':[],'points':[]}
import html
for p in re.findall(r'<Placemark>(.*?)</Placemark>',s,re.S):
    name=html.unescape(re.search(r'<name>(.*?)</name>',p,re.S).group(1)).strip()
    d=re.search(r'<description><!\[CDATA\[(.*?)\]\]>',p,re.S);d=html.unescape(d.group(1)) if d else ''
    col=re.search(r'<color>(.*?)</color>',p).group(1)
    co=[prj(*map(float,x.split(',')[:2])) for x in re.search(r'<coordinates>(.*?)</coordinates>',p,re.S).group(1).split()]
    if '<LineString>' in p: out['lines'].append({'name':name,'desc':d,'color':col,'pts':co})
    else: out['points'].append({'name':name,'color':col,'p':co[0]})
json.dump(out,open('data/kml.json','w'),ensure_ascii=False)
for l in out['lines']: print(l['color'],l['name'][:50].replace('\n',' '),len(l['pts']))
# route pts for JS (corridor)
rt=[l['pts'] for l in out['lines'] if l['color'] in('ff8136b6','ff3360fb','ff00ccff','ff54c93c')]
open('data/corridor.js','w').write(json.dumps([[[round(a),round(b)] for a,b in r] for r in rt],separators=(',',':')))
print(len(open('data/corridor.js').read()))
