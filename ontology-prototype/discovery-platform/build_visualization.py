"""Embed model and precomputed bounded views into the literal visualization fragment."""
import argparse
import json
from pathlib import Path
from explore import explore

ROOT=Path(__file__).resolve().parent

def main():
    args=argparse.ArgumentParser();args.add_argument('output',type=Path);options=args.parse_args()
    model=json.loads((ROOT/'model.json').read_text(encoding='utf-8'))
    previews={}
    for q in model['queries']:
        for depth in (1,2):
            for cap in (5,10,15,20,25,30):
                result=explore(model,q['id'],{'max_depth':depth,'max_nodes':cap})
                previews[f"{q['id']}|{depth}|{cap}"]={k:result[k] for k in ['node_ids','relation_ids','counts','recommendations','query_ambiguities','unresolved_indicators','budget_stop_reasons']}
    system={'nodes':[
      {'id':'user','label':'사용자 질문','x':.5,'y':0,'kind':'component'},
      {'id':'api','label':'FastAPI','x':.5,'y':.13,'kind':'component'},
      {'id':'harness','label':'Harness · 예산 예약','x':.5,'y':.27,'kind':'component'},
      {'id':'interpret','label':'질의 해석','x':.22,'y':.43,'kind':'component'},
      {'id':'llm','label':'외부 Luna / Sol','x':.82,'y':.43,'kind':'external'},
      {'id':'graph','label':'개념·관계 DB','x':.22,'y':.61,'kind':'storage'},
      {'id':'metadata','label':'메타데이터 DB','x':.78,'y':.61,'kind':'storage'},
      {'id':'check','label':'출처·조건·예산 검사','x':.5,'y':.78,'kind':'component'},
      {'id':'result','label':'자료·이유·URL','x':.18,'y':.97,'kind':'component'},
      {'id':'audit','label':'감사·요청 상태 정리','x':.82,'y':.97,'kind':'storage'}],
      'edges':[
        {'source':'user','target':'api'},{'source':'api','target':'harness'},
        {'source':'harness','target':'interpret'},{'source':'interpret','target':'llm','optional':True},
        {'source':'harness','target':'llm','optional':True},{'source':'harness','target':'metadata','optional':True},
        {'source':'interpret','target':'graph'},{'source':'graph','target':'metadata'},{'source':'metadata','target':'check'},
        {'source':'check','target':'llm','optional':True},{'source':'check','target':'result'},{'source':'result','target':'audit'}]}
    value={'model':{k:model[k] for k in ['version','nodes','relations','queries','source_evidence']},'previews':previews,'system':system}
    encoded=json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=(ROOT/'explorer.template.html').read_text(encoding='utf-8')
    fragment=template.replace('__DISCOVERY_DATA__',encoded)
    if len(fragment.encode())>=1_000_000:raise ValueError('Visualization byte limit exceeded')
    options.output.parent.mkdir(parents=True,exist_ok=True)
    options.output.write_text(fragment,encoding='utf-8')
    print(json.dumps({'path':str(options.output),'bytes':len(fragment.encode()),'bounded_views':len(previews)},ensure_ascii=False))

if __name__=='__main__':main()
