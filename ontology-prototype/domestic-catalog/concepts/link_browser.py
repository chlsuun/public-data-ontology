"""Enable existing catalog detail links without replacing the catalog UI."""
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'browser.html'
s=p.read_text(encoding='utf-8')
needle='await search()}catch(err)'
if needle in s:
    s=s.replace(needle,"await search();const selectedRecord=new URLSearchParams(location.search).get('record');if(selectedRecord)await detail(selectedRecord)}catch(err)",1)
    p.write_text(s,encoding='utf-8')
print('Catalog deep links ready')
