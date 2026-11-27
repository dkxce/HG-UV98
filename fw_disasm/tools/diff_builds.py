import sys, collections, hashlib, re
sys.path.insert(0,"tools")
import re_disasm as R

def load(path):
    fw=R.Firmware(path)
    fw.scan_strings(); fw.mark_fill(); fw.sweep(); fw.build_symbols()
    return fw

A=load("v101/V1.0.1_190619-KT.bin")            # old
B=load("Lanchonlh HG-UV98 Radio Firmware V1.2_211026.bin")   # new

# ---- string diff
sa=set(t for t,e,n in A.strings.values())
sb=set(t for t,e,n in B.strings.values())
added=sorted(sb-sa); removed=sorted(sa-sb)
with open("out/diff_strings.txt","w",encoding="utf-8") as f:
    f.write("# strings added in V1.2_211026 (%d)\n"%len(added))
    for t in added: f.write("+ %s\n"%t)
    f.write("\n# strings removed in V1.2_211026 (%d)\n"%len(removed))
    for t in removed: f.write("- %s\n"%t)
print("strings: old %d, new %d, added %d, removed %d"%(len(sa),len(sb),len(added),len(removed)))

# ---- function fingerprint diff
def fp(fw, fn):
    end=fw.func_end(fn)
    toks=[]
    for off in range(fn,end):
        ins=fw.insns.get(off)
        if ins is None: continue
        ops=re.sub(r"0x[0-9a-f]+","#",ins.op_str)
        ops=re.sub(r"#0x[0-9a-f]+","#",ops)
        toks.append(ins.mnemonic+" "+ops)
    return hashlib.md5("\n".join(toks).encode()).hexdigest(), len(toks)

fpa={fn:fp(A,fn) for fn in A.func_starts}
fpb={fn:fp(B,fn) for fn in B.func_starts}
h2a=collections.defaultdict(list)
for fn,(h,n) in fpa.items(): h2a[h].append(fn)
matched=[]
for fn,(h,n) in fpb.items():
    if h in h2a and n>=6:
        matched.append((fn,h2a[h][0],n))
print("functions: old %d, new %d, identical bodies %d"%(len(A.func_starts),len(B.func_starts),len(matched)))
deltas=collections.Counter((nb-na)//2*2 for nb,na,n in matched)
print("most common address shifts (new-old):", [(hex(k),v) for k,v in deltas.most_common(6)])
with open("out/diff_functions.csv","w",encoding="utf-8") as f:
    f.write("new_addr,old_addr,insns,delta\n")
    for nb,na,n in sorted(matched):
        f.write("%08X,%08X,%d,%+d\n"%(B.label(nb),A.label(na),n,nb-na))
