from lark import Lark, Token
from lark.visitors import Interpreter
import re, sys

grammar = """
program: (line*)

line: [LABELC] [stmt] [COMMENT] _NL

LABELC: CNAME ":"
COMMENT: /;.*/
IMMINT: "#" INT
IMMLABEL: "#" CNAME
LABEL: CNAME

?target: LABEL | INT
?imm: IMMINT | IMMLABEL
?dst: REG
?src1: REG
?src2: REG
REG: /R[0-9]|PC/i

stmt: "JP" target -> jp
    | "LD" dst "," imm -> ldi
    | "LD" dst "," src1 -> ld
    | "ADD" dst "," src1 "," src2 -> add
    | "SUB" dst "," src1 "," src2 -> sub
    | "NEG" dst "," src1 -> neg
    | "MUL" dst "," src1 "," src2 -> mul
    | "DIV" dst "," src1 "," src2 -> div
    | ("MOD"|"REM") dst "," src1 "," src2 -> mod
    | "ROUND" dst "," src1 -> round
    | "FLOOR" dst "," src1 -> floor

%import common.NEWLINE -> _NL
%import common.WS_INLINE
%import common.WORD
%import common.CNAME
%import common.INT

%ignore WS_INLINE
"""

class Assembler(Interpreter):
    NAME = "AEGIS BrickRigs CPU 0.6 Assembler"
    
    def __init__(self):
        self.labels: dict[str, int] = {}
        self.clear()
        
    def clear(self):
        self.listing = f"; {Assembler.NAME}\n;\n"

    def assemble(self, tree):
        # pass 1 - collect labels
        self.address = 0
        self.line = self.line_pass1
        self.visit(tree)

        # pass 2 - emit code
        print(self.listing, end='')  # header55
        self.address = 0
        self.line = self.line_pass2
        self.visit(tree)         
    
    def line_pass1(self, token):
        children = token.children
        label = children[0].value[:-1] if children[0] else None
        stmt = children[1]
        if label:
            self.labels[label] = self.address
        if stmt:
            self.address += 1        
        
    def word_3addr(self, ops):
        dst = self.reg(ops[0])
        src1 = self.reg(ops[1])
        src2 = self.reg(ops[2])
        return dst*100 + src1*10 + src2        

    def word_2addr(self, ops):
        dst = self.reg(ops[0])
        src1 = self.reg(ops[1])
        return dst*100 + src1*10
    
    def word_dstimm(self, ops):
        dst = self.reg(ops[0])
        imm = self.imm(ops[1])
        return dst*100 + imm
    
    def word_jump(self, ops):
        return self.target(ops[0])
    
    def word_none(self, _) -> int:
        return 0
    
    INSTRUCTIONS = {
        'add':   (0, word_3addr),    
        'ld':    (0, word_2addr),     
        'neg':   (1000, word_2addr),  
        'sub':   (2000, word_3addr),  #ok
        'mul':   (3000, word_3addr),
        'div':   (4000, word_3addr),  #ok
        'mod':   (5000, word_3addr),  #ok
        'round': (6000, word_2addr),  #ok
        'ldi':   (7000, word_dstimm), #ok
        'jp':    (7900, word_jump),   #ok
        'floor': (8000, word_2addr),  #ok
    }

    def line_pass2(self, token):        
        children = token.children
        label = children[0].value[:-1] if children[0] else ''
        stmt = children[1]
        comment = children[2] if children[2] else ''
        word = ''
        instr = ''
        ops = [Token('','')]
                
        if stmt:
            instr = stmt.data
            ops = stmt.children
            fmt = Assembler.INSTRUCTIONS[instr]
            word = fmt[0] + fmt[1](self, ops)
                
        textops = []
        for op in ops:
            textops.append(op.value)

        if label or stmt or comment:
            inops = f"{instr:5} {', '.join(textops)}"
            line = f"{self.address:0>2} {word:4} {label:8}  {inops:20} {comment}\n"
            print(line, end='')
            self.listing += line
            
        if label:
            assert(self.labels[label] == self.address)

        if stmt:
            self.address += 1
            
    def error(self, token: Token, msg: str):
        print(f"{token.line}:{token.column} Error: {msg}", file=sys.stderr)        
    
    def reg(self, token: Token):
        if re.match("pc", token.value, re.IGNORECASE):
            return 9
        return int(token.value[1])
    
    def imm(self, token: Token):
        if token.type == 'IMMINT':
            val = int(token.value[1:])
            if val<0:
                self.error(token, f"literal {val} must be non-negative")
                val = 0
            elif val>99:
                self.error(token, f"literal {val} must be less than 100")
                val = 99
            return val
        if token.type == 'IMMLABEL':
            target = self.labels.get(token.value)
            if target is None:
                self.error(token, f"unknown label {token.value}")
                target = 0
            return target
        return None
        
    def target(self, token: Token):
        if token.type == 'INT':
            val = int(token.value)
            if val<0:
                self.error(token, f"literal {val} must be non-negative")
                val = 0
            elif val>99:
                self.error(token, f"literal {val} must be less than 100")
                val = 99
            return val
        if token.type == 'LABEL':
            target = self.labels.get(token.value)
            if target is None:
                self.error(token, f"unknown label '{token.value}'")
                target = 0
            return target
        return None

parser = Lark(grammar, start='program', parser='lalr', propagate_positions=True)
asm = Assembler()

defaulttext = """
loop:    LD r3, #10          ; divisor
         DIV r1, r2, r3      ; r1 = r2 / 10
         MOD r2, r2, r3      ; r2 = r2 % 10
         FLOOR r1, r1        ; r1 = ⌊r2 / 10⌋
         JP loop
"""


if __name__=="__main__":
    import tkinter as tk
    
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
   
    def assemble():
        text = txt_edit.get("1.0", tk.END)
        thetree = parser.parse(text)
        asm.clear()
        asm.assemble(thetree)
        txt_listing.delete("1.0", tk.END)
        txt_listing.insert(tk.END, asm.listing)
        
    app = tk.Tk()
    app.title(Assembler.NAME)        

    app.rowconfigure(0, minsize=400, weight=1)
    app.rowconfigure(1, minsize=400, weight=1)
    app.columnconfigure(1, minsize=800, weight=1)
    
    font = ("Courier New", 14)
    padding = {'padx': 5, 'pady': 5}
    txt_edit = tk.Text(app, font=font)
    txt_listing = tk.Text(app, font=font)
    btn_assemble = tk.Button(app, text="Assemble", command=assemble)
    txt_edit.grid(row=0, column=1, sticky="nsew", **padding)
    txt_listing.grid(row=1, column=1, sticky="nsew", **padding)
    btn_assemble.grid(row=0, column=0, sticky="new", **padding)

    txt_edit.insert(tk.END, defaulttext)
    
    app.mainloop()
