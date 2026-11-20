import sys,os,csv,re,json,glob,collections
sys.path.insert(0,os.path.expanduser('~')); from dbcl import DBC
H=os.path.expanduser('~/mcat/'); csv.field_size_limit(10**9)
def P(p): return p.lower().replace('\\','/')
# 1. files in our MPQs, with the highest-priority archive that has them
order=sorted(glob.glob(H+'ls/base_*.tsv'))+sorted(glob.glob(H+'ls/rel_*.tsv'),key=lambda s:(len(os.path.basename(s)),s))
where={}
for f in order:
    tag=os.path.basename(f)[:-4].replace('base_','stock ').replace('rel_','')
    for l in open(f,encoding='latin1'):
        p=P(l.split('\t',1)[0])
        if p.startswith(('creature/','item/')) and p.endswith(('.m2','.blp')): where[p]=tag
print('files',len(where))
D=H+'dbc/DBFilesClient/'
cmd=DBC(D+'CreatureModelData.dbc'); cdi=DBC(D+'CreatureDisplayInfo.dbc'); idi=DBC(D+'ItemDisplayInfo.dbc')
def m2(s):
    s=P(s); return re.sub(r'\.(mdx|mdl)$','.m2',s)
cmd_path={r[0]:m2(cmd.str(r[2])) for r in cmd.rows()}
used_models=set(cmd_path.values())
disp_by_cmd=collections.Counter(r[1] for r in cdi.rows())
# skins used: texture variation names live in the model's folder
used_skins=set()
for r in cdi.rows():
    folder=cmd_path.get(r[1],'').rsplit('/',1)[0]
    for i in (6,7,8):
        if r[i]:
            n=cdi.str(r[i]).lower()
            if n: used_skins.add(folder+'/'+n+'.blp')
# item: model base names and texture base names
used_imodel=set(); used_itex=set()
for r in idi.rows():
    for i in (1,2):
        if r[i]:
            n=idi.str(r[i]).lower()
            if n: used_imodel.add(re.sub(r'\.(mdx|mdl|m2)$','',n))
    for i in range(15,23):
        if r[i]:
            n=idi.str(r[i]).lower()
            if n: used_itex.add(n)
# 2. retail tables
fd={}
for l in open(H+'lf2.csv',encoding='utf8',errors='replace'):
    a,b=l.rstrip('\n').split(';',1); fd[b.lower()]=int(a)
def rd(n): return csv.DictReader(open(H+n+'.csv',encoding='utf8',errors='replace'))
rcmd=collections.defaultdict(list)
for r in rd('creaturemodeldata'): rcmd[int(r['FileDataID'] or 0)].append(int(r['ID']))
rcdi=collections.defaultdict(list); rcdi_tex=collections.defaultdict(list)
for r in rd('creaturedisplayinfo'):
    rcdi[int(r['ModelID'])].append(int(r['ID']))
    for k,v in r.items():
        if k.startswith('TextureVariationFileDataID') and v and v!='0': rcdi_tex[int(v)].append(int(r['ID']))
npc_by_disp=collections.defaultdict(list); npcname={}
for r in rd('creature'):
    i=int(r['ID']); npcname[i]=r['Name_lang']
    for k in range(4):
        v=r.get('DisplayID[%d]'%k)
        if v and v!='0': npc_by_disp[int(v)].append(i)
mres=collections.defaultdict(list)
for r in rd('modelfiledata'): mres[int(r['FileDataID'])].append(int(r['ModelResourcesID']))
tres=collections.defaultdict(list)
for r in rd('texturefiledata'): tres[int(r['FileDataID'])].append(int(r['MaterialResourcesID']))
idi_by_mres=collections.defaultdict(list)
for r in rd('itemdisplayinfo'):
    for k in ('ModelResourcesID[0]','ModelResourcesID[1]'):
        if r[k] and r[k]!='0': idi_by_mres[int(r[k])].append(int(r['ID']))
idi_by_tres=collections.defaultdict(list)
for r in rd('itemdisplayinfomaterialres'): idi_by_tres[int(r['MaterialResourcesID'])].append(int(r['ItemDisplayInfoID']))
app_by_idi=collections.defaultdict(list)
for r in rd('itemappearance'): app_by_idi[int(r['ItemDisplayInfoID'])].append(int(r['ID']))
items_by_app=collections.defaultdict(list)
for r in rd('itemmodifiedappearance'): items_by_app[int(r['ItemAppearanceID'])].append(int(r['ItemID']))
itemname={}
for r in rd('itemsparse'): itemname[int(r['ID'])]=r['Display_lang']
def npcs_for_disps(ds):
    out=[]
    for d in ds:
        for n in npc_by_disp.get(d,[]):
            if n not in out: out.append(n)
    return out
def npcs_for_model(path):
    f=fd.get(path)
    if not f: return None,[]
    ds=[d for c in rcmd.get(f,[]) for d in rcdi.get(c,[])]
    return f,npcs_for_disps(ds)
def items_for_idis(idis):
    out=[]
    for d in idis:
        for a in app_by_idi.get(d,[]):
            for it in items_by_app.get(a,[]):
                if it not in out: out.append(it)
    return out
def items_for_model(path):
    f=fd.get(path)
    if not f: return None,[]
    return f,items_for_idis([d for m in mres.get(f,[]) for d in idi_by_mres.get(m,[])])
def items_for_tex(path):
    f=fd.get(path)
    if not f: return None,[]
    return f,items_for_idis([d for m in tres.get(f,[]) for d in idi_by_tres.get(m,[])])
rows=[]
def add(kind,path,f,ids,isnpc,note=''):
    names=npcname if isnpc else itemname
    good=[i for i in ids if names.get(i)]
    rows.append(dict(kind=kind,path=path,mpq=where[path],retail=('yes' if f else 'no'),
        ids=good[:3],names=[names[i] for i in good[:3]],total=len(good),npc=isnpc,note=note))
skip=re.compile(r'(_hd|_lod\d|\d\d\.skin)')
# creature models without a model row, or with a row but no display
cmd_by_path={}
for k,v in cmd_path.items(): cmd_by_path.setdefault(v,k)
for p in sorted(where):
    if not p.startswith('creature/'): continue
    if p.endswith('.m2'):
        if p not in used_models:
            f,n=npcs_for_model(p); add('Creature model (no model row)',p,f,n,True)
        elif disp_by_cmd.get(cmd_by_path[p],0)==0:
            f,n=npcs_for_model(p); add('Creature model (row, no display)',p,f,n,True,'model row %d'%cmd_by_path[p])
    elif p.endswith('.blp'):
        folder=p.rsplit('/',1)[0]
        if folder+'/'+p.rsplit('/',1)[1].split('.')[0]+'.m2' in where: continue  # model texture of same name, skip
        if any(m.startswith(folder+'/') for m in ()): pass
        if p in used_skins: continue
        # only folders whose model is shown in the client: new skins for an existing creature
        mods=[m for m in used_models if m.startswith(folder+'/')]
        if not mods: continue
        f=fd.get(p); n=npcs_for_disps(rcdi_tex.get(f,[])) if f else []
        if n: add('Creature skin (unused variation)',p,f,n,True,'model '+mods[0].rsplit('/',1)[1])
def ibase(p):
    b=p.rsplit('/',1)[1][:-3]
    b=re.sub(r'_(hu|or|dw|ni|sc|ta|gn|tr|be|dr|go|wo|pa|vu|nb|vr|lf|kt|zt|dt|mg|ma|ea|ha|ev)_?[mf]$','',b)
    return b
for p in sorted(where):
    if p.startswith('item/objectcomponents/') and p.endswith('.m2'):
        b=ibase(p)
        if b not in used_imodel:
            f,n=items_for_model(p); add('Item model ('+p.split('/')[2]+')',p,f,n,False)
seen_tex=set()
for p in sorted(where):
    if p.startswith('item/texturecomponents/') and p.endswith('.blp'):
        b=re.sub(r'_[mfu]$','',p.rsplit('/',1)[1][:-4])
        if b in used_itex or b in seen_tex: continue
        seen_tex.add(b)
        f,n=items_for_tex(p)
        if n: add('Armor texture ('+p.split('/')[2]+')',p,f,n,False)
json.dump(rows,open(H+'catalog.json','w'))
c=collections.Counter((r['kind'],r['total']>0) for r in rows)
for k,v in sorted(c.items()): print(k,v)
# ---- group into catalogue rows
REG=set('chest belt pant pants boot boots glove gloves bracer bracers robe sleeve sleeves tu tl au al lu ll hand foot fo ha cape shirt tabard waist wrist legs leg shoulder helm'.split())
def setkey(b):
    t=b.split('_')
    while len(t)>1 and t[-1] in REG: t.pop()
    return '_'.join(t)
out=[]; groups=collections.OrderedDict()
for r in rows:
    k=r['kind']
    if k.startswith('Item model (collections)'): continue
    if k.startswith('Armor texture'):
        b=re.sub(r'_[mfu]$','',r['path'].rsplit('/',1)[1][:-4]); key=('Armor set',setkey(b))
        part=r['path'].split('/')[2].replace('texture','')
    elif k.startswith('Item model'):
        b=ibase(r['path']); b=re.sub(r'^[lr](shoulder_)',r'\1',b); key=(k,b); part=''
    else:
        out.append(dict(kind=k,name=r['path'].split('/')[-1][:-3] if r['path'].endswith('.m2') else r['path'].split('/')[-1][:-4],
            path=r['path'],mpq=r['mpq'],ids=r['ids'],names=r['names'],npc=True,parts='',note=r['note'])); continue
    g=groups.setdefault(key,dict(kind=key[0],name=key[1],path=r['path'],mpq=r['mpq'],ids=[],names=[],npc=False,parts=set(),note=''))
    if part: g['parts'].add(part)
    for i,n in zip(r['ids'],r['names']):
        if i not in g['ids'] and len(g['ids'])<3: g['ids'].append(i); g['names'].append(n)
for g in groups.values(): g['parts']=', '.join(sorted(g['parts'])); out.append(g)
json.dump(out,open(H+'catalog2.json','w'))
print(collections.Counter(o['kind'] for o in out)); print('with link',sum(1 for o in out if o['ids']),'of',len(out))
