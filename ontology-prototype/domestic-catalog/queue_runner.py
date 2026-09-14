"""Bounded, resumable metadata queues with visible, honest progress."""
from common import *
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from collections import deque

def ordered_pages(function,pages,stop,workers=2):
    """Keep only a small window of page futures, including on cooperative stop."""
    pages=iter(pages)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending=deque()
        try:
            while True:
                while len(pending)<workers*2 and not stop.exists():
                    page=next(pages,None)
                    if page is None:break
                    pending.append(pool.submit(function,page))
                if not pending or stop.exists():break
                yield pending.popleft().result()
        finally:
            for future in pending:future.cancel()

def run_queue(name,targets,collect,workers=2,limited=False):
    targets=list(targets);iterator=iter(targets);processed=0;fields=0;counts={};started=now()
    report=HERE/(name+('-adapter-check.json' if limited else '-collection-report.json'))
    stop=ROOT/'.local/domestic-catalog'/(name+'.stop')
    last=time.monotonic()
    def progress():
        dump(report,{'scope':name,'target_count':len(targets),'processed':processed,
            'remaining':len(targets)-processed,'status_counts':counts,
            'documented_field_occurrences':fields,'queue_exhausted':processed==len(targets),
            'all_columns_complete':False,'started_at':started,'generated_at':now(),'pid':os.getpid()})
    progress()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending=set()
        while True:
            while len(pending)<workers*2 and not stop.exists():
                row=next(iterator,None)
                if row is None:break
                pending.add(pool.submit(collect,row))
            if not pending:break
            done,pending=wait(pending,return_when=FIRST_COMPLETED,timeout=10)
            for future in done:
                item=future.result();processed+=1;fields+=len(item.get('fields',[]))
                status=item['status'];counts[status]=counts.get(status,0)+1
            if time.monotonic()-last>20:
                progress();print(name,processed,'/',len(targets),counts,flush=True);last=time.monotonic()
    progress();print('QUEUE_END',name,processed,counts,flush=True)
