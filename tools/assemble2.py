import json,sys,re
parts={};n=None
for f in sys.argv[2:]:
    a=json.load(open(f)); t=a[0]['text'].strip()
    s=json.JSONDecoder().raw_decode(t)[0] if t.startswith('"') else t
    s=s.rstrip()
    m=re.match(r'CHUNK(\d+)/(\d+)\|',s); i=int(m.group(1)); n=int(m.group(2))
    assert s.endswith('|END'),(f,s[-60:]); parts[i]=s[m.end():-4]
assert sorted(parts)==list(range(n)),(sorted(parts),n)
open(sys.argv[1],'w').write(''.join(parts[i] for i in range(n)))
print('ok',sum(len(p) for p in parts.values()))
