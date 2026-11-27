import sys, csv, collections, re
sys.path.insert(0,"tools")
import re_disasm as R

def analyse(path, label, outdir):
    fw=R.Firmware(path)
    fw.scan_strings(); fw.mark_fill(); fw.sweep(); fw.build_symbols()
    # peripheral references
    periph=collections.Counter(); ram=collections.Counter()
    for off,ins in fw.insns.items():
        for op in ins.operands:
            addrs=[]
            if op.type==R.capstone.arm.ARM_OP_MEM and not op.mem.index and op.mem.disp>=0x40000000:
                addrs.append(op.mem.disp)
            if ins.mnemonic.startswith("ldr") and op.type==R.capstone.arm.ARM_OP_MEM and op.mem.base==R.capstone.arm.ARM_REG_PC:
                lit=((ins.address+4)&~3)+op.mem.disp-R.BASE
                v=fw.u32(lit)
                if v: addrs.append(v)
            for a in addrs:
                nm=R.periph_name(a)
                if nm: periph[nm.split("+")[0]]+=1
                elif 0x20000000<=a<0x20010000: ram[(a//0x1000)*0x1000]+=1
    callers=collections.Counter()
    calls=collections.Counter()
    for off,ins in fw.insns.items():
        if ins.mnemonic in ("bl","blx") and ins.operands and ins.operands[0].type==R.capstone.arm.ARM_OP_IMM:
            t=ins.operands[0].imm-R.BASE
            callers[t]+=1
            calls[off]+=1
    strs=list(fw.strings.values())
    cn=sum(1 for t,e,n in strs if e=="gb2312")
    vec=fw.vectors()
    uniq=len(set(v for i,nm,v,o in vec[16:]))
    print("=== %s"%label)
    print("  insns %d, funcs %d, strings %d (gb2312 %d)"%(len(fw.insns),len(fw.func_starts),len(strs),cn))
    print("  unique IRQ vectors: %d/60"%uniq)
    print("  peripherals:", ", ".join("%s:%d"%(k,v) for k,v in periph.most_common(14)))
    print("  top called functions:", ", ".join("%08X(%d)"%(fw.label(k),v) for k,v in callers.most_common(10)))
    print("  RAM blocks:", ", ".join("%08X:%d"%(k,v) for k,v in ram.most_common(8)))
    with open(outdir+"/string_texts.txt","w",encoding="utf-8") as f:
        for t,e,n in strs:
            if len(t)>=4: f.write(t+"\n")
    return fw

analyse("Lanchonlh HG-UV98 Radio Firmware V1.2_211026.bin","V1.2_211026","out")
analyse("v101/V1.0.1_190619-KT.bin","V1.0.1_190619-KT","out_v101")
