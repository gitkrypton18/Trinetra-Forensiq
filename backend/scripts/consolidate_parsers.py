import os
def consolidate(base_name):
    old_file = f"backend/parsers_{base_name}.py"
    new_file = f"backend/parsers/{base_name}.py"
    
    if not os.path.exists(old_file):
        return
        
    with open(old_file, 'r', encoding='utf-8') as f:
        old_lines = f.readlines()
    with open(new_file, 'r', encoding='utf-8') as f:
        new_lines = f.readlines()
    
    # Filter out _v2 imports
    new_lines = [l for l in new_lines if f"from .. import parsers_{base_name} as _v2" not in l]
    # Filter out future imports
    new_lines = [l for l in new_lines if "from __future__ import annotations" not in l]
    
    # Replace _v2 calls
    new_lines = [l.replace("_v2.", "") for l in new_lines]
    
    merged = "".join(old_lines) + "\n\n" + "".join(new_lines)
    
    with open(new_file, 'w', encoding='utf-8') as f:
        f.write(merged)
        
    os.remove(old_file)

consolidate("bank")
consolidate("cdr")
consolidate("ipdr")
