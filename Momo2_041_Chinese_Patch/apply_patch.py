"""Install/check/remove a strictly versioned, additive Momodora II Chinese patch."""
import argparse,json,re,sys,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'tools'))
from gm7_momo2 import *
BASE=Path(__file__).resolve().parent
OUTPUT='momodora2_zh.exe'
RECEIPT='momo2_zh_install.json'

def manifest():
    m=json.loads((BASE/'patch.json').read_text(encoding='utf-8'))
    need(m['format']=='momodora2-041-zh-source-v1' and m['original_sha256']==ORIGINAL,'Invalid patch format')
    need(set(m['assets'])=={'momo2_zh_text.png','momo2_zh_ctrl.png','atlas_layout.json'},'Unexpected asset list')
    for name,sha in m['assets'].items():need(digest((BASE/'assets'/name).read_bytes())==sha,'Asset checksum mismatch: '+name)
    return m

def hook(code):
    code=re.sub(rb'\bdraw_text\(([^\r\n]*?),string_copy\(currentstr,1,pos\)\)',rb'zh_dialogue(\1,currentstr,pos)',code)
    return re.sub(rb'\b(draw_text(?:_transformed_color|_transformed|_color|_ext_color|_ext)?)\s*(?=\()',lambda x:b'zh_'+x[1],code)

def make_patched(exe,m):
    plain=unpack_exe(exe,original=True)
    need(digest(plain[SCRIPTS:FONT])==m['script_table_sha256'],'Script table checksum mismatch')
    helpers={r['slot']:r for r in m['allocated']};hooks={r['name']:r['before_sha256'] for r in m['script_hooks']}
    need(len(helpers)==8,'Unexpected helper count');table=bytearray(pack(400,COUNT))
    for row in scripts(plain):
        if row['name']:
            need(row['slot'] not in helpers,'Refusing to replace existing script')
            if row['name'] in hooks:
                need(digest(row['code'])==hooks[row['name']],'Source script mismatch')
                table.extend(pack(1)+field(row['name'].encode('ascii'))+pack(400)+script_record(hook(row['code'])))
            else:table.extend(plain[row['begin']:row['end']])
        elif row['slot'] in helpers:
            r=helpers[row['slot']];code=m['helpers'][r['name']].encode('ascii')
            need(digest(code)==r['sha256'],'Helper checksum mismatch')
            table.extend(pack(1)+field(r['name'].encode('ascii'))+pack(400)+script_record(code))
        else:table.extend(pack(0))
    edits=[(SCRIPTS,FONT,bytes(table))]
    for row in m['inline']:
        p=row['offset'];n=row['before_length'];old=plain[p+4:p+4+n]
        need(u32(plain,p)==n and digest(old)==row['before_sha256'],'Inline source mismatch')
        edits.append((p,p+4+n,field(row['after'].encode('ascii'))))
    newplain=apply_edits(plain,edits)
    need(digest(newplain)==m['payload_sha256'],'Patched payload checksum mismatch')
    result=repack_exe(exe,newplain)
    need(result[:OFFSET]==exe[:OFFSET] and unpack_exe(result)==newplain,'Patched readback failed')
    return result

def apply(root,check=False,remove=False):
    root=Path(root).resolve();m=manifest();original=root/'momodora2.exe'
    exe=original.read_bytes();need(digest(exe)==ORIGINAL,'Unsupported/modified original EXE. Nothing was overwritten.')
    dest=root/'data/graphics/misc';need(dest.is_dir(),'Missing original data/graphics/misc directory')
    out=root/OUTPUT;receipt=dest/RECEIPT
    targets={out:None}
    targets.update({dest/name:sha for name,sha in m['assets'].items()})
    if remove:
        need(receipt.is_file(),'No installation receipt; nothing removed')
        r=json.loads(receipt.read_text(encoding='utf-8'));need(r['format']==m['format'],'Invalid receipt')
        targets[out]=r['exe_sha256']
        for file,sha in targets.items():
            if file.exists():need(digest(file.read_bytes())==sha,'Installed file modified; refusing removal: '+file.name)
        for file in targets:
            if file.exists():file.unlink()
        receipt.unlink();return {'removed':True,'original_unchanged':digest(original.read_bytes())==ORIGINAL,'saves_untouched':True}
    result=make_patched(exe,m);targets[out]=digest(result)
    status={'mode':'check' if check else 'install','original_unchanged':True,'readback_verified':True,'output_sha256':digest(result),'payload_sha256':m['payload_sha256'],'target_matches_build':digest(result)==m['target_sha256']}
    # Preflight every target before writing anything. Never touch original resources or saves.
    for file,sha in targets.items():
        if file.exists():need(digest(file.read_bytes())==sha,'Existing file differs; move it first: '+file.name)
    if receipt.exists():
        old=json.loads(receipt.read_text(encoding='utf-8'));need(old.get('exe_sha256')==digest(result) and old.get('format')==m['format'],'Existing receipt differs')
    if check:return status
    created=[]
    try:
        for file in targets:
            if not file.exists():
                data=result if file==out else (BASE/'assets'/file.name).read_bytes()
                with file.open('xb') as f:f.write(data)
                created.append(file)
        if not receipt.exists():
            r={'format':m['format'],'version':m['version'],'exe_sha256':digest(result),'assets':m['assets']}
            with receipt.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
            created.append(receipt)
    except Exception:
        for file in reversed(created):file.unlink(missing_ok=True)
        raise
    need(digest(original.read_bytes())==ORIGINAL,'Original changed unexpectedly')
    status['output']=str(out);return status

def main():
    p=argparse.ArgumentParser(description='Momodora II v041 Simplified Chinese patch')
    p.add_argument('--game-dir',type=Path,default=BASE.parent);g=p.add_mutually_exclusive_group();g.add_argument('--check',action='store_true');g.add_argument('--remove',action='store_true');a=p.parse_args()
    print(json.dumps(apply(a.game_dir,a.check,a.remove),ensure_ascii=False,indent=2))
if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,zlib.error) as e:print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
