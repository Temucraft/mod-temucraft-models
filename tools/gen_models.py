# Builds mod-temucraft-models: display rows, creatures and cosmetic items for the free models in our client,
# plus cosmetic outfits from city guards' equipment. Reads our client DBCs (patch-T), MPQ listings, retail tables.
import sys,os,csv,re,json,glob,collections,struct
sys.path.insert(0,os.path.expanduser('~')); from dbcl import DBC
H=os.path.expanduser('~/mcat/'); csv.field_size_limit(10**9)
CORE=os.path.expanduser('~/mnt/TemuCraft Server/1) Source/data/sql/base/db_world/')
def P(p): return p.lower().replace('\\','/')
# ---------- what our client has
where={}
order=sorted(glob.glob(H+'ls/base_*.tsv'))+sorted(glob.glob(H+'ls/rel_*.tsv'),key=lambda s:(len(os.path.basename(s)),s))
for f in order:
    for l in open(f,encoding='latin1'):
        p=P(l.split('\t',1)[0])
        if p.startswith(('creature/','item/','interface/icons/')) and p.endswith(('.m2','.blp')): where[p]=1
icons={p.rsplit('/',1)[1][:-4] for p in where if p.startswith('interface/icons/')}
D=H+'dbc/DBFilesClient/'
cmd=DBC(D+'CreatureModelData.dbc'); cdi=DBC(D+'CreatureDisplayInfo.dbc'); idi=DBC(D+'ItemDisplayInfo.dbc'); cdx=DBC(D+'CreatureDisplayInfoExtra.dbc')
def m2(s): return re.sub(r'\.(mdx|mdl)$','.m2',P(s))
cmd_path={r[0]:m2(cmd.str(r[2])) for r in cmd.rows()}
# ---------- retail
fd={}; fdpath={}
for l in open(H+'lf2.csv',encoding='utf8',errors='replace'):
    a,b=l.rstrip('\n').split(';',1); b=b.lower(); fd[b]=int(a); fdpath[int(a)]=b
def rd(n): return csv.DictReader(open(H+n+'.csv',encoding='utf8',errors='replace'))
I=lambda v:int(float(v)) if v not in ('',None) else 0
F=lambda v:float(v) if v not in ('',None) else 0.0
rcmd_by_fd=collections.defaultdict(list); rcmd={}
for r in rd('creaturemodeldata'): rcmd[I(r['ID'])]=r; rcmd_by_fd[I(r['FileDataID'])].append(I(r['ID']))
rcdi={}; rcdi_by_cmd=collections.defaultdict(list)
for r in rd('creaturedisplayinfo'):
    i=I(r['ID']); rcdi[i]=r; rcdi_by_cmd[I(r['ModelID'])].append(i)
rcre={}
for r in rd('creature'): rcre[I(r['ID'])]=r
mres=collections.defaultdict(list)
for r in rd('modelfiledata'): mres[I(r['ModelResourcesID'])].append(I(r['FileDataID']))
tres=collections.defaultdict(list)
for r in rd('texturefiledata'): tres[I(r['MaterialResourcesID'])].append(I(r['FileDataID']))
ridi={}
for r in rd('itemdisplayinfo'): ridi[I(r['ID'])]=r
matres=collections.defaultdict(list)
for r in rd('itemdisplayinfomaterialres'): matres[I(r['ItemDisplayInfoID'])].append((I(r['ComponentSection']),I(r['MaterialResourcesID'])))
appidi={}
for r in rd('itemappearance'): appidi[I(r['ID'])]=I(r['ItemDisplayInfoID'])
item_app={}
for r in rd('itemmodifiedappearance'):
    it=I(r['ItemID']); mod=I(r['ItemAppearanceModifierID'])
    if it not in item_app or mod==0: item_app[it]=I(r['ItemAppearanceID'])
ritem={}
for r in rd('item'): ritem[I(r['ID'])]=r
rsparse={}
for r in rd('itemsparse'): rsparse[I(r['ID'])]=(r['Display_lang'],I(r['OverallQualityID']))
print('loaded',len(where),len(rcre),len(ritem))
# ---------- ids (variables in the SQL)
BASE=dict(CMD=46000,CDI=1210000,IDI=1210000,CRE=1210000,ITEM=1210000,OUT=1220000,ODI=1220000,SET=4000)
cat=json.load(open(H+'catalog2.json'))
cmd_by_path={}
for k,v in cmd_path.items(): cmd_by_path.setdefault(v,k)
def fexists(p): return P(p) in where
def tex_name(fdid, folder):
    """A retail texture by file id -> its name in the model's folder, if our client has it there."""
    p=fdpath.get(fdid)
    if not p: return ''
    n=p.rsplit('/',1)[1]
    return n[:-4] if (folder+'/'+n) in where else ''
TYPE_MAP={i:i for i in range(0,14)}; TYPE_MAP.update({14:12,15:10})
out=dict(cmd=[],cdi=[],cmi=[],cre=[],ctm=[],idi=[],item=[],itemdbc=[],loot=[])
n=collections.Counter(); skipped=collections.Counter()
used_names=set()
# ---------- creatures
for r in cat:
    k=r['kind']
    if not k.startswith('Creature') or not r['ids']: continue
    path=r['path']; folder=path.rsplit('/',1)[0]
    npc=None; disp=None
    for nid in r['ids']:
        c=rcre.get(nid)
        if not c: continue
        for j in range(4):
            d=I(c.get('DisplayID[%d]'%j))
            if not d or d not in rcdi: continue
            rc=rcmd.get(I(rcdi[d]['ModelID']))
            if not rc: continue
            mp=fdpath.get(I(rc['FileDataID']),'')
            if k.startswith('Creature skin'):
                tx=[fdpath.get(I(rcdi[d]['TextureVariationFileDataID[%d]'%t]),'') for t in range(3)]
                if path in tx and mp.rsplit('/',1)[0]==folder: npc,disp=c,d; break
            elif mp==path: npc,disp=c,d; break
        if npc: break
    if not npc: skipped['creature: no retail display']+=1; continue
    rd_=rcdi[disp]; rc=rcmd[I(rd_['ModelID'])]
    if k.startswith('Creature model (no model row)'):
        mid=('CMD',len(out['cmd']))
        g=[F(rc['GeoBox[%d]'%i]) for i in range(6)]
        out['cmd'].append([mid,0,path.replace('/','\\').replace('.m2','.mdx'),min(max(I(rc['SizeClass']),0),4),F(rc['ModelScale']) or 1.0,
                           1 if I(rc['BloodID']) else 0,0,0.0,0.0,1.0,0,0,0,0,F(rc['CollisionWidth']),F(rc['CollisionHeight']),F(rc['MountHeight'])]+g+[1.0,1.0,0.0,0.0,0.0])
    else:
        mp=fdpath.get(I(rc['FileDataID']),'')
        if mp not in cmd_by_path: skipped['creature: model row missing']+=1; continue
        mid=cmd_by_path[mp]
    tex=[tex_name(I(rd_['TextureVariationFileDataID[%d]'%t]),folder) for t in range(3)]
    if k.startswith('Creature skin') and not any(tex): skipped['skin: texture missing']+=1; continue
    did=('CDI',len(out['cdi']))
    scale=F(rd_['CreatureModelScale']) or 1.0
    out['cdi'].append([did,mid,0,0,scale,255,tex[0],tex[1],tex[2],'',0,0,0,0,0,0])
    cw=F(rc['CollisionWidth']) or 0.5
    br=round(max(0.2,cw*scale*0.5),3); cr=round(max(1.0,br*2.5),3)
    out['cmi'].append([did,br,cr,2,0])
    cid=('CRE',len(out['cre']))
    name=npc['Name_lang'] or r['name']
    sub='Model: '+r['name']
    out['cre'].append([cid,name,sub,TYPE_MAP.get(I(npc['CreatureType']),10)])
    out['ctm'].append([cid,did])
    n['creatures']+=1
# ---------- items from the free models
def ibase(p):
    b=p.rsplit('/',1)[1][:-3]
    return re.sub(r'_(hu|or|dw|ni|sc|ta|gn|tr|be|dr|go|wo|pa|vu|nb|vr|lf|kt|zt|dt|mg|ma|ea|ha|ev)_?[mf]$','',b)
objfiles=collections.defaultdict(set)
for p in where:
    if p.startswith('item/objectcomponents/') and p.endswith('.m2'): objfiles[p.rsplit('/',1)[0]].add(ibase(p))
def model_name(mid, side=None):
    # side 'l' or 'r' for shoulders: the left and the right pad are two files
    for f in mres.get(mid,[]):
        p=fdpath.get(f,'')
        if not p.startswith('item/objectcomponents/') or not p.endswith('.m2'): continue
        b=ibase(p)
        if side and not (b.endswith('_'+side) or b.startswith(side+'shoulder')): continue
        if b in objfiles[p.rsplit('/',1)[0]]: return b
    return None
def model_tex(mid):
    for f in tres.get(mid,[]):
        p=fdpath.get(f,'')
        if p in where and p.startswith('item/objectcomponents/'): return p.rsplit('/',1)[1][:-4]
    return None
def body_tex(mid):
    # the client adds _M, _F or _U to the name itself, so only files named that way can be used
    for f in tres.get(mid,[]):
        p=fdpath.get(f,'')
        if p in where and p.startswith('item/texturecomponents/') and re.search(r'_[mfu]\.blp$',p):
            return p.rsplit('/',1)[1][:-6]
    return None
FALLBACK_ICON={1:'INV_Helmet_01',3:'INV_Shoulder_01',4:'INV_Shirt_01',5:'INV_Chest_Chain',6:'INV_Belt_01',7:'INV_Pants_01',8:'INV_Boots_01',
               9:'INV_Bracer_01',10:'INV_Gauntlets_01',16:'INV_Misc_Cape_01',19:'INV_Shirt_GuildTabard_01',20:'INV_Chest_Cloth_01',14:'INV_Shield_01',
               23:'INV_Misc_Book_01',13:'INV_Sword_01',17:'INV_Sword_01',21:'INV_Sword_01',22:'INV_Sword_01',15:'INV_Weapon_Bow_01',25:'INV_Throwingknife_01',26:'INV_Weapon_Rifle_01'}
def icon_for(it, inv):
    p=fdpath.get(I(it.get('IconFileDataID')),'')
    if p.startswith('interface/icons/'):
        n_=p.rsplit('/',1)[1][:-4]
        if n_ in icons: return n_
    f=FALLBACK_ICON.get(inv,'INV_Misc_QuestionMark')
    return f if f.lower() in icons else 'INV_Misc_QuestionMark'
def map_class(c,s):
    if c==2: return 2,(7 if s==9 else (s if s<=20 else 14))
    if c==4: return 4,(0 if s in (5,) or s>10 else s)
    return None
def add_item(name,cls,sub,inv,disp,quality,material,sheath,desc,flags=0):
    iid=('ITEM',len(out['item']))
    out['item'].append(dict(id=iid,cls=cls,sub=sub,name=name,disp=disp,q=quality,inv=inv,mat=material,sheath=sheath,desc=desc,flags=flags))
    out['itemdbc'].append([iid,cls,sub,-1,material,disp,inv,sheath])
    return iid
for r in cat:
    k=r['kind']
    if not (k.startswith('Item model') or k=='Armor set') or not r['ids']: continue
    if any(w in k for w in ('backpack','battlestandards','pouch','quiver','scroll','collections')): continue  # the 3.3.5 body has no slot for these
    done=False
    for itid in r['ids']:
        it=ritem.get(itid); app=item_app.get(itid)
        if not it or app is None: continue
        rid=appidi.get(app); ri=ridi.get(rid)
        if not ri: continue
        cm=map_class(I(it['ClassID']),I(it['SubclassID']))
        inv=I(it['InventoryType'])
        if not cm or not (0<inv<=28): continue
        models=['','']; mtex=['','']; ok=True
        for j in (0,1):
            mr=I(ri['ModelResourcesID[%d]'%j]) or (I(ri['ModelResourcesID[0]']) if inv==3 and j==1 else 0)
            if mr:
                mn=model_name(mr,('l','r')[j] if inv==3 else None)
                if mn is None: ok=False; break
                models[j]=mn+'.mdx'
                tr=I(ri['ModelMaterialResourcesID[%d]'%j]) or (I(ri['ModelMaterialResourcesID[0]']) if inv==3 and j==1 else 0)
                if tr:
                    t=model_tex(tr)
                    if t is None: ok=False; break
                    mtex[j]=t
        if not ok or any(m.lower().startswith(('backpack','quiver','pouch','collections')) for m in models if m): continue
        body=['']*8
        for sec,mr in matres.get(rid,[]):
            if sec>7: continue
            t=body_tex(mr)
            if t is None: ok=False; break
            body[sec]=t
        if not ok: continue
        # the look must use this catalogue entry's file
        key=r['name'].lower()
        if k=='Armor set':
            if not any(b.lower().startswith(key) for b in body if b): continue
        elif not any(m.lower().startswith(key) for m in models if m): continue
        g=[I(ri['GeosetGroup[%d]'%i]) for i in range(3)]
        icon=icon_for(it,inv)
        did=('IDI',len(out['idi']))
        out['idi'].append([did,models[0],models[1],mtex[0],mtex[1],icon,'',g[0],g[1],g[2],0,0,0,0,0]+body+[0,0])
        nm,q=rsparse.get(itid,(r['name'],2))
        q=min(max(q,1),4)
        add_item(nm,cm[0],cm[1],inv,did,q,I(it['Material']) if 0<=I(it['Material'])<=8 else 0,I(it['SheatheType']) if 0<=I(it['SheatheType'])<=7 else 0,'Cosmetic look.')
        n['items']+=1; done=True; break
    if not done: skipped['item: no complete retail look']+=1
# ---------- outfits: what NPCs wear, as cosmetic item sets (city guards, then every elite, rare and boss)
def tuples(path, want=None):
    rx=re.compile(r"^\((\d+),")
    for line in open(path,encoding='utf8',errors='replace'):
        m=rx.match(line)
        if m and (want is None or int(m.group(1)) in want):
            yield next(csv.reader([line.strip().rstrip(',;')[1:-1]],quotechar="'",escapechar='\\'))
GUARDS=[68,1976,1756,5595,727,4262,16733,3296,14304,5624,3084,16222]
gname={}; grank={}
for t in tuples(CORE+'creature_template.sql'):
    gname[int(t[0])]=t[6]; grank[int(t[0])]=int(t[20])
gmodels=collections.defaultdict(list)
for t in tuples(CORE+'creature_template_model.sql'): gmodels[int(t[0])].append(int(t[2]))
gequip=collections.defaultdict(list)
for t in tuples(CORE+'creature_equip_template.sql'):
    if int(t[1])==1: gequip[int(t[0])]+= [int(x) for x in t[2:5] if int(x)]
wanted_items={i for v in gequip.values() for i in v}
stock={}
for t in tuples(CORE+'item_template.sql',wanted_items):
    stock[int(t[0])]=dict(cls=int(t[1]),sub=int(t[2]),name=t[4],disp=int(t[5]),q=int(t[6]),inv=int(t[12]))
CB=cdi.byid(); XB=cdx.byid(); IB=idi.byid()
SLOTS=[(1,'Helm'),(3,'Shoulders'),(4,'Shirt'),(5,'Tunic'),(6,'Belt'),(7,'Leggings'),(8,'Boots'),(9,'Bracers'),(10,'Gloves'),(19,'Tabard'),(16,'Cloak')]
WEAPON={0:'Axe',1:'Greataxe',2:'Bow',3:'Gun',4:'Mace',5:'Maul',6:'Polearm',7:'Sword',8:'Greatsword',10:'Staff',13:'Fist Weapon',15:'Dagger',16:'Throwing Weapon',17:'Spear',18:'Crossbow',19:'Wand'}
IDI_FMT='issssssiiiiiiiissssssssii'
def armor_sub(d,inv):
    if inv in (4,19): return 0
    if inv==16: return 1
    names=' '.join(idi.str(IB[d][k]).lower() for k in (1,2,3,4,15,16,17,18,19,20,21,22) if IB[d][k])
    for word,sub in (('plate',4),('mail',3),('chain',3),('leather',2),('cloth',1),('robe',1)):
        if word in names: return sub
    return 1
box_disp=next((i for i,r in IB.items() if r[5] and idi.str(r[5]).lower()=='inv_box_01'),None) or next(i for i,r in IB.items() if r[5] and idi.str(r[5]).lower().startswith('inv_misc_bag'))
iconed={}
def with_icon(d,inv):
    """The display itself if it has an icon; else a copy of it with the slot's plain icon."""
    if IB[d][5] and idi.str(IB[d][5]): return d
    if d in iconed: return iconed[d]
    row=[ (idi.str(v) if f=='s' and v else ('' if f=='s' else v)) for v,f in zip(IB[d],IDI_FMT)]
    f=FALLBACK_ICON.get(inv,'INV_Misc_QuestionMark'); row[5]=f if f.lower() in icons else 'INV_Misc_QuestionMark'
    row[0]=('ODI',len(out['odi'])); out['odi'].append(row); iconed[d]=row[0]; return row[0]
out['odi']=[]; out['oitem']=[]; out['oitemdbc']=[]; out['set']=[]; out['oloot']=[]
def add_oitem(name,cls,sub,inv,disp,material,desc,flags=0):
    iid=('OUT',len(out['oitem']))
    out['oitem'].append(dict(id=iid,cls=cls,sub=sub,name=name,disp=disp,q=2,inv=inv,mat=material,sheath=0,desc=desc,flags=flags,set=0))
    out['oitemdbc'].append([iid,cls,sub,-1,material,disp,inv,0])
    return iid
outfit_of={}   # item tuple -> creature that names it
order_=GUARDS+sorted((e for e in gname if grank.get(e,0)>=1 and e not in GUARDS), key=lambda e:(-grank[e],e))
for e in order_:
    for d in gmodels.get(e,[]):
        ext=CB.get(d,(0,0,0,0))[3]
        if not ext or ext not in XB: continue
        items=tuple(XB[ext][8:19])
        if sum(1 for i,v in enumerate(items) if v and i not in (2,9))<4 and e not in GUARDS: continue
        if not any(items) or items in outfit_of: continue
        outfit_of[items]=(e,XB[ext][2])
count_by_name=collections.Counter()
outfits=[]
for items,(e,sex) in outfit_of.items():
    who0=gname.get(e,'Stranger').strip() or 'Stranger'
    who=who0+"'" if who0.endswith('s') else who0+"'s"
    count_by_name[who0]+=1
    tag='' if count_by_name[who0]==1 else ' '+['','','II','III','IV','V','VI','VII','VIII','IX','X'][min(count_by_name[who0],10)]
    pieces=[]
    for (inv,word),d in zip(SLOTS,items):
        if not d or d not in IB: continue
        inv2=20 if inv==5 and IB[d][9] else inv
        pieces.append(add_oitem(f"{who} {word}{tag}",4,armor_sub(d,inv2),inv2,with_icon(d,inv2),0,'Cosmetic look.'))
    if count_by_name[who0]==1:
        for it in gequip.get(e,[]):
            st=stock.get(it)
            if not st or st['cls'] not in (2,4) or not st['disp']: continue
            word=WEAPON.get(st['sub'],'Weapon') if st['cls']==2 else 'Shield'
            pieces.append(add_oitem(f"{who} {word}",st['cls'],st['sub'],st['inv'],st['disp'],0,'Cosmetic look.'))
    if len(pieces)<2: continue
    sid=('SET',len(out['set']))
    setname=f"{who} Outfit{tag}"
    out['set'].append([sid,setname]+[pc for pc in pieces[:17]])
    for pc in pieces: out['oitem'][pc[1]]['set']=sid
    box=add_oitem(setname,15,0,0,box_disp,0,'Open it for the whole look.',flags=4)
    for pc in pieces: out['oloot'].append([box,pc])
    outfits.append(setname); n['outfit pieces']+=len(pieces)
n['outfits']=len(outfits)
print(n, dict(skipped)); print('outfits',len(outfits),outfits[:12])
if os.environ.get('SAMPLE'):
    import random; random.seed(3)
    for x in random.sample(out['idi'],6): print('IDI',x)
    for x in random.sample(out['item'],6): print('ITEM',x)
    for x in random.sample(out['cdi'],4): print('CDI',x)
    for x in random.sample(out['cre'],4): print('CRE',x)
    for x in out['cmd'][:2]: print('CMD',x)
# ---------- write
MOD=os.path.expanduser('~/mnt/TemuCraft Server/1) Source/modules/mod-temucraft-models/')
def num(v): return BASE[v[0]]+v[1] if isinstance(v,tuple) else v
def sq(v):
    if isinstance(v,tuple): return '@%s+%d'%v
    if isinstance(v,float): return repr(round(v,6))
    if isinstance(v,int): return str(v)
    return "'"+str(v).replace('\\','\\\\').replace("'","\\'")+"'"
def block(table,cols,rows,per=500):
    o=[]
    for i in range(0,len(rows),per):
        o.append('INSERT INTO `%s` (%s) VALUES\n%s;\n'%(table,', '.join('`%s`'%c for c in cols),
                 ',\n'.join('('+', '.join(sq(v) for v in r)+')' for r in rows[i:i+per])))
    return ''.join(o)
SZ=dict(CMD=2999,CDI=9999,IDI=9999,CRE=9999,ITEM=9999,OUT=39999,ODI=39999,SET=2999)
head=['-- mod-temucraft-models: generated by tools/gen_models.py, do not edit by hand.',
      '-- Display rows, showcase creatures and fully cosmetic items for models that ship in the Temucraft client patches',
      '-- but had no display row, plus cosmetic outfits from city guards. Ids are the variables below; every block deletes its',
      '-- own range first, so the file can be run again. The client needs the same rows (client/DBFilesClient).',
      'SET @CMD  := %d; -- CreatureModelData'%BASE['CMD'],'SET @CDI  := %d; -- CreatureDisplayInfo'%BASE['CDI'],
      'SET @IDI  := %d; -- ItemDisplayInfo'%BASE['IDI'],'SET @CRE  := %d; -- creature_template'%BASE['CRE'],
      'SET @ITEM := %d; -- item_template, Item.dbc (looks from the free models)'%BASE['ITEM'],
      'SET @OUT  := %d; -- item_template, Item.dbc (NPC outfits)'%BASE['OUT'],
      'SET @ODI  := %d; -- ItemDisplayInfo (NPC looks given an icon)'%BASE['ODI'],
      'SET @SET  := %d; -- ItemSet (one per outfit)'%BASE['SET'],'']
sql=['\n'.join(head)]
def dele(t,c,v): sql.append('DELETE FROM `%s` WHERE `%s` BETWEEN @%s AND @%s+%d;\n'%(t,c,v,v,SZ[v]))
dele('creaturemodeldata_dbc','ID','CMD')
sql.append(block('creaturemodeldata_dbc',['ID','Flags','ModelName','SizeClass','ModelScale','BloodID','FootprintTextureID','FootprintTextureLength','FootprintTextureWidth','FootprintParticleScale','FoleyMaterialID','FootstepShakeSize','DeathThudShakeSize','SoundID','CollisionWidth','CollisionHeight','MountHeight','GeoBoxMinX','GeoBoxMinY','GeoBoxMinZ','GeoBoxMaxX','GeoBoxMaxY','GeoBoxMaxZ','WorldEffectScale','AttachedEffectScale','MissileCollisionRadius','MissileCollisionPush','MissileCollisionRaise'],out['cmd']))
dele('creaturedisplayinfo_dbc','ID','CDI')
sql.append(block('creaturedisplayinfo_dbc',['ID','ModelID','SoundID','ExtendedDisplayInfoID','CreatureModelScale','CreatureModelAlpha','TextureVariation_1','TextureVariation_2','TextureVariation_3','PortraitTextureName','BloodLevel','BloodID','NPCSoundID','ParticleColorID','CreatureGeosetData','ObjectEffectPackageID'],out['cdi']))
dele('creature_model_info','DisplayID','CDI')
sql.append(block('creature_model_info',['DisplayID','BoundingRadius','CombatReach','Gender','DisplayID_Other_Gender'],out['cmi']))
dele('creature_template_model','CreatureID','CRE'); dele('creature_template','entry','CRE')
sql.append(block('creature_template',['entry','name','subname','minlevel','maxlevel','faction','npcflag','unit_class','unit_flags','type','speed_walk','speed_run'],
                 [[c[0],c[1],c[2],1,1,35,0,1,2|256|512,c[3],1.0,1.14286] for c in out['cre']]))
sql.append(block('creature_template_model',['CreatureID','Idx','CreatureDisplayID','DisplayScale','Probability'],[[c[0],0,c[1],1.0,1.0] for c in out['ctm']]))
dele('itemdisplayinfo_dbc','ID','IDI')
sql.append(block('itemdisplayinfo_dbc',['ID','ModelName_1','ModelName_2','ModelTexture_1','ModelTexture_2','InventoryIcon_1','InventoryIcon_2','GeosetGroup_1','GeosetGroup_2','GeosetGroup_3','Flags','SpellVisualID','GroupSoundIndex','HelmetGeosetVis_1','HelmetGeosetVis_2','Texture_1','Texture_2','Texture_3','Texture_4','Texture_5','Texture_6','Texture_7','Texture_8','ItemVisual','ParticleColorID'],out['idi']))
dele('itemdisplayinfo_dbc','ID','ODI')
sql.append(block('itemdisplayinfo_dbc',['ID','ModelName_1','ModelName_2','ModelTexture_1','ModelTexture_2','InventoryIcon_1','InventoryIcon_2','GeosetGroup_1','GeosetGroup_2','GeosetGroup_3','Flags','SpellVisualID','GroupSoundIndex','HelmetGeosetVis_1','HelmetGeosetVis_2','Texture_1','Texture_2','Texture_3','Texture_4','Texture_5','Texture_6','Texture_7','Texture_8','ItemVisual','ParticleColorID'],out['odi']))
for v in ('ITEM','OUT'):
    dele('item_loot_template','Entry',v); dele('item_dbc','ID',v); dele('item_template','entry',v)
ICOLS=['entry','class','subclass','SoundOverrideSubclass','name','displayid','Quality','Flags','BuyCount','BuyPrice','SellPrice','InventoryType','AllowableClass','AllowableRace','ItemLevel','RequiredLevel','maxcount','stackable','bonding','description','Material','sheath','delay','dmg_min1','dmg_max1','MaxDurability','itemset']
def irow(i): return [i['id'],i['cls'],i['sub'],-1,i['name'],i['disp'],i['q'],i['flags'],1,0,0,i['inv'],-1,-1,1,1,0,1,1,i['desc'],i['mat'],i['sheath'],2000 if i['cls']==2 else 0,1 if i['cls']==2 else 0,2 if i['cls']==2 else 0,0,i.get('set',0)]
sql.append(block('item_template',ICOLS,[irow(i) for i in out['item']+out['oitem']]))
sql.append(block('item_dbc',['ID','ClassID','SubclassID','Sound_Override_Subclassid','Material','DisplayInfoID','InventoryType','SheatheType'],out['itemdbc']+out['oitemdbc']))
sql.append(block('item_loot_template',['Entry','Item','Reference','Chance','QuestRequired','LootMode','GroupId','MinCount','MaxCount','Comment'],
    [[b,pc,0,100.0,0,1,0,1,1,'outfit piece'] for b,pc in out['loot']+out['oloot']]))
dele('itemset_dbc','ID','SET')
LOCS=['enUS','enGB','koKR','frFR','deDE','enCN','zhCN','enTW','zhTW','esES','esMX','ruRU','ptPT','ptBR','itIT','Unk']
def setrow(r):
    ids=list(r[2:])+[0]*(17-len(r[2:]))
    return [r[0]]+[r[1]]*16+[16712190]+ids+[0]*18
sets_sql=[setrow(r) for r in out['set']]
sql.append(block('itemset_dbc',['ID']+['Name_Lang_'+l for l in LOCS]+['Name_Lang_Mask']+['ItemID_%d'%i for i in range(1,18)]+['SetSpellID_%d'%i for i in range(1,9)]+['SetThreshold_%d'%i for i in range(1,9)]+['RequiredSkill','RequiredSkillRank'],sets_sql))
if not os.environ.get('DRY'):
    os.makedirs(MOD+'data/sql/db-world/base',exist_ok=True)
    open(MOD+'data/sql/db-world/base/temucraft_models.sql','w',encoding='utf8').write('\n'.join(sql))
    # client DBCs: patch-T's tables with our rows appended
    def write_dbc(src,dst,rows,fmt):
        d=DBC(src); recs=[d.d[20+i*d.rs:20+(i+1)*d.rs] for i in range(d.n)]
        strings=bytearray(d.d[d.st:d.st+d.ss]); sidx={}
        def soff(t):
            if not t: return 0
            if t in sidx: return sidx[t]
            o=len(strings); strings.extend(t.encode('latin1')+b'\0'); sidx[t]=o; return o
        drop={num(r[0]) for r in rows}
        recs=[x for x in recs if struct.unpack_from('<I',x)[0] not in drop]
        for r in rows:
            vals=[]
            for v,f in zip(r,fmt):
                v=num(v)
                vals.append(struct.pack('<I',soff(v)) if f=='s' else struct.pack('<f',float(v)) if f=='f' else struct.pack('<i',int(v)))
            assert len(vals)==d.fc,(len(vals),d.fc); recs.append(b''.join(vals))
        os.makedirs(os.path.dirname(dst),exist_ok=True)
        open(dst,'wb').write(b'WDBC'+struct.pack('<4I',len(recs),d.fc,d.rs,len(strings))+b''.join(recs)+bytes(strings))
    C=MOD+'client/DBFilesClient/'
    write_dbc(D+'CreatureModelData.dbc',C+'CreatureModelData.dbc',out['cmd'],'iisifiiiffiiiiffffffffffffff')
    write_dbc(D+'CreatureDisplayInfo.dbc',C+'CreatureDisplayInfo.dbc',out['cdi'],'iiiifissssiiiiii')
    write_dbc(D+'ItemDisplayInfo.dbc',C+'ItemDisplayInfo.dbc',out['idi']+out['odi'],'issssssiiiiiiiissssssssii')
    write_dbc(D+'Item.dbc',C+'Item.dbc',out['itemdbc']+out['oitemdbc'],'iiiiiiii')
    write_dbc(D+'ItemSet.dbc',C+'ItemSet.dbc',sets_sql,'i'+'s'*16+'i'*36)
    json.dump({k:[[list(x) if isinstance(x,tuple) else x for x in (r if isinstance(r,list) else [r])] for r in v] for k,v in out.items()},open(H+'rows.json','w'))
print('rows',{k:len(v) for k,v in out.items()})
