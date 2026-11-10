import re,json,sys
S='./'
t=open(S+'types.block').read()
types={}   # name -> dict(kind, rows, note, rhs, base)
aggs=[];cur=None
lines=t.split('\n');i=0
def field(l):
    m=re.match(r'\s+([^?:\s]+)(\?)?: (.*?)(?:\s+// (.*))?$',l)
    n,o,ty,c=m.group(1),bool(m.group(2)),m.group(3).strip(),m.group(4) or ''
    k=''
    mk=re.match(r'(PK・FK|PK|FK)(?:。|$)(.*)',c)
    if mk:k,c=mk.group(1),mk.group(2)
    return [n,o,ty,c,k]
while i<len(lines):
    l=lines[i]
    if l.startswith('// ====='):
        cur={'title':l[9:].strip(),'root':True,'rule':'','types':[]};aggs.append(cur)
    elif l.startswith('// -----'): cur=None
    elif l.startswith('// 守ること: '): cur['rule']=l[len('// 守ること: '):]
    elif l.startswith('type '):
        m=re.match(r'type ([^\s<=]+)(?:<[^=]*(?:=[^>]*)?>)? = (.*)$',l)
        name,rhs=m.group(1),m.group(2)
        note=''
        if '//' in rhs: rhs,note=[x.strip() for x in rhs.split('//',1)]
        if rhs.endswith('{'):
            base=rhs[:-1].strip().rstrip('&').strip() or None
            rows=[];i+=1
            while not lines[i].startswith('}'): rows.append(field(lines[i]));i+=1
            types[name]={'kind':'obj','rows':rows,'note':note,'base':base}
        else:
            types[name]={'kind':'alias','rhs':rhs,'note':note}
        if cur is not None: cur['types'].append(name)
    i+=1
def rows(n):
    T=types[n]
    return (rows(T['base']) if T.get('base') else [])+T['rows']
def is_enum(n): 
    T=types[n];return T['kind']=='alias' and "'" in T['rhs']
def is_union(n):
    T=types[n];return T['kind']=='alias' and "'" not in T['rhs'] and ' | ' in T['rhs']
boxable=[n for n,T in types.items() if T['kind']=='obj' or is_enum(n) or is_union(n)]
def box(n):
    T=types[n]
    if T['kind']=='obj': return {'name':n,'note':T['note'],'rows':rows(n)}
    if is_enum(n): return {'name':n,'note':T['note'],'rows':[['',False,T['rhs'],'','']]}
    return {'name':n,'note':T['note'],'rows':[['次のどれか',False,T['rhs'],'','']]}
def refs(b):
    out=[]
    for r in b['rows']:
        for n in boxable:
            if re.search(r'(^|[^\w])'+re.escape(n)+r'(?![\w])',re.sub(r"'[^']*'",'',r[2])) and n!=b['name']: out.append(n)
    return out
bases={T['base'] for T in types.values() if T.get('base')}
A=[]
for g in aggs:
    order=[];todo=[g['types'][0]]
    while todo:
        n=todo.pop(0)
        if n in order or n in bases: continue
        order.append(n);todo+=refs(box(n))
    A.append({'title':g['title'],'root':True,'rule':g['rule'],'boxes':[box(n) for n in order]})
enums=[n for n in boxable if is_enum(n) and types[n]['rhs'].count("'")<=24]
h=open(S+'index.html').read()
m=re.search(r'const AGGS=(\[.*?\]);\n',h,re.S)
h=h[:m.start(1)]+json.dumps(A,ensure_ascii=False)+h[m.end(1):]
h=re.sub(r'const ENUMBOX=new Set\(\[.*?\]\);','const ENUMBOX=new Set('+json.dumps(enums,ensure_ascii=False)+');',h)
open(S+'index.html','w').write(h)
print([ (a['title'][:8],[b['name'] for b in a['boxes']]) for a in A]);print(enums)
