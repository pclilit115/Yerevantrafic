import json,sys,re
parts={}
for f in sys.argv[2:]:
    a=json.load(open(f)); t=a[0]['text']
    t=t.strip()
    # text may be a JSON string literal followed by tab context
    if t.startswith('"'):
        end=t.index('"\n') if '"\n' in t else len(t)
        s=json.JSONDecoder().raw_decode(t)[0]
    else: s=t
    m=re.match(r'CHUNK(\d+)/(\d+)\|',s); i=int(m.group(1)); n=int(m.group(2))
    body=s[m.end():]; assert body.endswith('|END'),(f,body[-50:]); parts[i]=body[:-4]
assert sorted(parts)==list(range(n)),(sorted(parts),n)
open(sys.argv[1],'w').write(''.join(parts[i] for i in range(n)))
d=json.load(open(sys.argv[1])); print('ok',type(d), list(d)[:5] if isinstance(d,dict) else len(d))
