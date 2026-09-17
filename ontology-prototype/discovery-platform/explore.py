"""Bounded in-memory demonstration; production must bound indexed DB reads too."""
from collections import defaultdict, deque
import json
from pathlib import Path
from time import monotonic

ROOT=Path(__file__).resolve().parent

def explore(model, query_id, overrides=None, clock=monotonic):
    limits=dict(model['policy']['ontology'])
    for key,value in (overrides or {}).items():
        if key not in limits or isinstance(value,bool) or not isinstance(value,int) or value<0:
            raise ValueError('Invalid graph limit: '+str(key))
        if value>limits[key]:raise ValueError('Override cannot exceed configured policy: '+key)
        limits[key]=value
    if limits['max_nodes']<1:raise ValueError('The query requires one root node')
    nodes={n['id']:n for n in model['nodes']}
    if query_id not in nodes or nodes[query_id]['type']!='query':raise ValueError('Unknown query')
    adjacency=defaultdict(list)
    for edge in model['relations']:adjacency[edge['source']].append(edge)
    for edges in adjacency.values():edges.sort(key=lambda e:(e['priority'],e['id']))
    selected={query_id};selected_edges={};parents={};seen={(query_id,0,0)}
    queue=deque([(query_id,0,0)])
    datasets=set();stops=set();scanned=0;started=clock()
    while queue:
        current,depth,structural=queue.popleft()
        if (clock()-started)*1000>=limits['query_timeout_ms']:
            stops.add('query_timeout_ms');break
        for edge in adjacency[current]:
            if (clock()-started)*1000>=limits['query_timeout_ms']:
                stops.add('query_timeout_ms');queue.clear();break
            if scanned>=limits['max_scanned_edges']:
                stops.add('max_scanned_edges');queue.clear();break
            scanned+=1
            next_depth=depth+edge['semantic_cost']
            next_structural=0 if edge['semantic_cost'] else structural+1
            if next_depth>limits['max_depth']:stops.add('max_depth');continue
            if next_structural>limits['max_structural_hops']:stops.add('max_structural_hops');continue
            target=edge['target'];new_node=target not in selected
            if new_node and len(selected)>=limits['max_nodes']:stops.add('max_nodes');continue
            if new_node and nodes[target]['type']=='dataset' and len(datasets)>=limits['max_datasets']:
                stops.add('max_datasets');continue
            if edge['id'] not in selected_edges and len(selected_edges)>=limits['max_edges']:
                stops.add('max_edges');continue
            selected_edges[edge['id']]=edge
            if new_node:
                selected.add(target);parents[target]=edge['id']
                if nodes[target]['type']=='dataset':datasets.add(target)
            state=(target,next_depth,next_structural)
            if state not in seen:seen.add(state);queue.append(state)
    def path_to(node_id):
        path=[];cursor=node_id
        while cursor!=query_id:
            edge=selected_edges[parents[cursor]];path.append(edge['id']);cursor=edge['source']
        return list(reversed(path))
    recommendations=[]
    for dataset_id in sorted(datasets):
        path=path_to(dataset_id);d=nodes[dataset_id]
        recommendations.append({'dataset_id':dataset_id,'path':path,
          'reason_kind':'hypothesis_path' if any(selected_edges[e]['role']=='context_hypothesis' for e in path) else 'direct_measure_path',
          'mapping_has_candidate':any(selected_edges[e]['status']=='candidate' for e in path),
          'source_url':d['source_url'],'evidence_ids':sorted({s for e in path for s in selected_edges[e]['evidence_ids']}),
          'join_allowed':False,'policy_decision':'discovery_only','unresolved_conditions':d['limitations']})
    elapsed=(clock()-started)*1000
    return {'query_id':query_id,'node_ids':sorted(selected),'relation_ids':list(selected_edges),
      'recommendations':recommendations,'counts':{'nodes':len(selected),'edges':len(selected_edges),'datasets':len(datasets),'scanned_edges':scanned},
      'limits':limits,'budget_stop_reasons':sorted(stops),'truncated':bool(stops),
      'unresolved_indicators':[i for i in sorted(selected) if nodes[i].get('data_gap')],
      'query_ambiguities':nodes[query_id]['ambiguities'],'elapsed_ms':round(elapsed,3),
      'llm_calls':0,'raw_rows_fetched':0,'runtime':'offline_demo','policy_version':model['policy']['version']}

if __name__=='__main__':
    model=json.loads((ROOT/'model.json').read_text(encoding='utf-8'))
    results={q['id']:explore(model,q['id']) for q in model['queries']}
    (ROOT/'example-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:r['counts'] for key,r in results.items()},ensure_ascii=False,indent=2))
