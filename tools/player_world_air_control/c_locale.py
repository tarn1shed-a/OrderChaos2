"""Explicit C-locale libc data ABI for original libstdc++ ASCII marker parsing.

This is an emulator runtime import, not an actor/game/asset success response.
The original ctype<char> code reads its imported _ctype_ pointer, adds one,
then tests the source bits. It is not an Android locale observation.
"""
def install(engine):
    # Bionic/BSD ctype byte layout consumed by the original ctype<char>.
    table=bytearray(257)
    for c in range(128):
        upper=65<=c<=90;lower=97<=c<=122;digit=48<=c<=57
        table[c+1]=(int(upper)|int(lower)<<1|int(digit)<<2|int(c in(9,10,11,12,13,32))<<3|
          int(33<=c<=126 and not(upper or lower or digit))<<4|int(c<32 or c==127)<<5|
          int(digit or 65<=c<=70 or 97<=c<=102)<<6|int(c==32)<<7)
    ptr=engine.alloc(len(table));engine.uc.mem_write(ptr,bytes(table));holder=engine.alloc(8);engine.w(holder,'Q',ptr);engine.w(0x2506408,'Q',holder)
    return{'scope':'explicit host C locale for original ASCII event strings','nativeImportedSymbol':'_ctype_','originalGOT':'2506408','originalGetter':'1d9e92c','nonASCIIEventsAdmitted':False}
