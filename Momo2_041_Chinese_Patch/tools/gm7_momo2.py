"""Strict reader/writer for Momodora II v041. Never alters the engine prefix."""
import hashlib,struct,zlib
ORIGINAL='a836f7b90daefe5f603663cdf65ddd10dda8a4eddf086d8c71e02fe71e563af3'
OFFSET=0x224B3D
START=14192
SEED=24329
SCRIPTS=131219
FONT=162374
COUNT=186

def need(ok,message):
    if not ok: raise ValueError(message)
def digest(data):return hashlib.sha256(data).hexdigest()
def u32(data,pos):return struct.unpack_from('<I',data,pos)[0]
def pack(*values):return struct.pack('<'+'I'*len(values),*values)
def field(value):return pack(len(value))+value
def tables(seed):
    table=list(range(256))
    for i in range(1,10001):
        j=1+(i*(6+seed%250)+seed//250)%254
        table[j],table[j+1]=table[j+1],table[j]
    return bytes(table),bytes(sorted(range(256),key=table.__getitem__))
def inflate(blob):
    d=zlib.decompressobj(); result=d.decompress(blob)+d.flush()
    need(d.eof and not d.unused_data and not d.unconsumed_tail,'Invalid zlib boundary')
    return result
def unpack_exe(exe,original=False):
    if original:need(digest(exe)==ORIGINAL,'Unsupported original Momodora II v041 EXE (SHA-256 mismatch)')
    need(u32(exe,OFFSET)==len(exe)-OFFSET-4,'Invalid game data length')
    raw=inflate(exe[OFFSET+4:]); n,m=struct.unpack_from('<II',raw)
    need((n,m,u32(raw,8+4*n))==(1061,2484,SEED),'Unexpected game data header')
    decoded=raw[START+1:].translate(tables(SEED)[1])
    plain=raw[:START+1]+bytes((v-i)&255 for i,v in enumerate(decoded,START+1))
    need(u32(plain,START)==2*SEED-1,'Invalid decryption sentinel')
    return plain
def repack_exe(exe,plain):
    raw=plain[:START+1]+bytes((v+i)&255 for i,v in enumerate(plain[START+1:],START+1)).translate(tables(SEED)[0])
    if raw==inflate(exe[OFFSET+4:]):return exe
    return exe[:OFFSET]+field(zlib.compress(raw,6))
def scripts(plain):
    need(struct.unpack_from('<II',plain,SCRIPTS)==(400,COUNT),'Unexpected script table')
    p=SCRIPTS+8; result=[]; inv=tables(12345)[1]
    for slot in range(COUNT):
        begin=p; flag=u32(plain,p);p+=4
        need(flag in (0,1),'Invalid script presence flag')
        row=dict(slot=slot,begin=begin,end=p,name=None,code=None)
        if flag:
            n=u32(plain,p);name=plain[p+4:p+4+n].decode('ascii');p+=4+n
            need(u32(plain,p)==400,'Invalid script version');p+=4
            end=p+4+u32(plain,p);code=inflate(plain[p+4:end]).translate(inv)
            need(u32(code,0)==len(code)-4,'Invalid script source length')
            row.update(end=end,name=name,code=code[4:]);p=end
        result.append(row)
    need(p==FONT,'Unexpected script table end')
    return result
def script_record(code):return field(zlib.compress(field(code).translate(tables(12345)[0]),6))
def apply_edits(plain,edits):
    result=bytearray();cursor=0
    for start,end,value in sorted(edits):
        need(cursor<=start<=end<=len(plain),'Overlapping edits')
        result.extend(plain[cursor:start]);result.extend(value);cursor=end
    result.extend(plain[cursor:]);return bytes(result)
