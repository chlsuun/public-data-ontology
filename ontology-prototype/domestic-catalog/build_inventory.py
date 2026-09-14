"""Import complete acquired catalog snapshots; never invent source schemas.

Run with the bundled Python (openpyxl), plus local beautifulsoup4/xlrd.
SQLite is a rebuildable local index. Portable normalized records are JSONL gzip.
"""
from common import *
from collections import Counter
from io import BytesIO, StringIO
from urllib.parse import urlsplit,parse_qs
import csv,re,sqlite3,zipfile

DB=ROOT/'.local/domestic-catalog/catalog.sqlite3'
OUT=HERE/'inventory'

def raw(name):return gzip.decompress((HERE/'evidence'/(name+'.raw.gz')).read_bytes())

class Inventory:
    def __init__(self):
        OUT.mkdir(exist_ok=True);DB.parent.mkdir(parents=True,exist_ok=True)
        self.temp=DB.with_suffix('.building.sqlite3')
        # This path belongs only to this generator; preserve the last complete DB.
        if self.temp.exists():self.temp.unlink()
        self.db=sqlite3.connect(self.temp)
        self.db.executescript('''
        PRAGMA foreign_keys=ON;
        CREATE TABLE records(id TEXT PRIMARY KEY, portal_id TEXT NOT NULL,
          dataset_key TEXT NOT NULL, title TEXT NOT NULL, provider_id TEXT,
          provider_name TEXT, kind TEXT, url TEXT, evidence_id TEXT,
          locator TEXT, output_raw TEXT, request_raw TEXT,
          schema_status TEXT, metadata_json TEXT NOT NULL);
        CREATE TABLE fields(record_id TEXT REFERENCES records(id), role TEXT,
          ordinal INTEGER, name TEXT, status TEXT,
          PRIMARY KEY(record_id,role,ordinal));
        CREATE TABLE documented_fields(record_id TEXT REFERENCES records(id),
          ordinal INTEGER, name TEXT, name_en TEXT, description TEXT, datatype TEXT,
          unit TEXT, definition_json TEXT, evidence_id TEXT,
          PRIMARY KEY(record_id,evidence_id,ordinal));
        CREATE TABLE quarantine(id INTEGER PRIMARY KEY, source TEXT, locator TEXT, reason TEXT, raw_json TEXT);
        ''')
        self.records=gzip.open(OUT/'catalog-records.jsonl.gz','wt',encoding='utf-8',newline='\n')
        self.quarantine=gzip.open(OUT/'quarantine.jsonl.gz','wt',encoding='utf-8',newline='\n')
        self.stats={}

    def add(self,r):
        self.records.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
        keys=['id','portal_id','dataset_key','title','provider_id','provider_name','kind',
              'url','evidence_id','locator','output_raw','request_raw','schema_status']
        self.db.execute('INSERT INTO records VALUES('+','.join('?' for _ in range(14))+')',
                        [r.get(k) for k in keys]+[json.dumps(r,ensure_ascii=False)])
        fields=[]
        for role,field in [('output','output_raw'),('request','request_raw')]:
            text=r.get(field) or ''
            # This export is a comma-separated label bag, not a schema. Commas
            # inside labels cannot be recovered without the source definition.
            for pos,label in enumerate(text.split(','),1):
                if label.strip():fields.append((r['id'],role,pos,label.strip(),'declared_token_unverified'))
        self.db.executemany('INSERT INTO fields VALUES(?,?,?,?,?)',fields)

    def reject(self,source,locator,reason,row):
        entry={'source':source,'locator':locator,'reason':reason,'raw':row}
        self.quarantine.write(json.dumps(entry,ensure_ascii=False)+'\n')
        self.db.execute('INSERT INTO quarantine(source,locator,reason,raw_json) VALUES(?,?,?,?)',
                        (source,locator,reason,json.dumps(row,ensure_ascii=False)))

    def data_go(self):
        rows=list(csv.reader(StringIO(raw('data-go-bulk').decode('cp949'),newline='')))
        header=rows[0]
        assert header==['목록키','목록명','키워드','제공기관명','제공기관코드','목록유형',
                        '서비스 유형','데이터포맷','요청변수','출력결과','주기','전체행']
        def valid(r):return len(r)==12 and re.fullmatch(r'\d{7,8}',r[0] or '') and r[5] in ('FILE','API','STD') and bool(r[3])
        bad={i for i,r in enumerate(rows[1:],1) if not valid(r)}
        # A malformed continuation can invalidate the preceding logical record.
        implicated=set()
        for i in bad:
            j=i-1
            while j in bad:j-=1
            if j>0:implicated.add(j)
        for i,r in enumerate(rows[1:],1):
            if i in bad or i in implicated:
                self.reject('data-go-bulk',f'csv_record:{i+1}',
                    'invalid_record_shape_or_identifiers' if i in bad else 'followed_by_malformed_continuation',r)
                continue
            key,title,kw,org,code,kind,service,fmt,req,out,period,total=r
            suffix={'FILE':'fileData','API':'openapi','STD':'standard'}[kind]
            self.add({'id':f'data-go-row-{i+1}','portal_id':'data-go',
                'dataset_key':key,'title':title,'provider_id':'data-go-org-'+code,
                'provider_name':org,'kind':kind,'url':f'https://www.data.go.kr/data/{key}/{suffix}.do',
                'evidence_id':'data-go-bulk','locator':f'csv_record:{i+1}',
                'output_raw':out or None,'request_raw':req or None,
                'schema_status':'declared_labels_only' if out else 'schema_not_in_catalog',
                'source_provider_code':code,'keywords_raw':kw,'service_type':service,
                'format_raw':fmt,'update_frequency_raw':period,'row_count_raw':total or None,
                'datatype':None,'unit':None,'code_system':None,'license':None,
                'time_coverage':None,'spatial_coverage':None,'dataset_version':None,
                'snapshot_label':'20260703','source_record_identity':'snapshot + row; repeated dataset keys preserved'})
        self.stats['data-go']={'source_rows':len(rows)-1,'imported_records':len(rows)-1-len(bad|implicated),
            'invalid_rows':len(bad),'implicated_rows':len(implicated),'advertised_rows':68943,
            'advertised_count_matches':len(rows)-1==68943,'encoding':'cp949',
            'snapshot_label':'20260703','all_current_portal_records_confirmed':False}
        self.db.commit()
        print('DATA_GO',json.dumps(self.stats['data-go']),flush=True)

    def seoul(self):
        import openpyxl
        w=openpyxl.load_workbook(BytesIO(raw('seoul-bulk')),read_only=True,data_only=True)
        total=0
        for s in w:
            for i,row in enumerate(s.iter_rows(values_only=True),1):
                if i==1:continue
                if not row[0]:continue
                if len(row)<11 or not str(row[0]).startswith('OA-'):
                    self.reject('seoul-bulk',f'{s.title}!A{i}:L{i}','unexpected_catalog_row',list(row[:12]));continue
                key,kind,title,desc,category,dept,created,modified,url,kw,state=row[:11]
                self.add({'id':f'seoul-row-{i}','portal_id':'seoul','dataset_key':key,
                    'title':title,'provider_id':None,'provider_name':None,'kind':kind,'url':url,
                    'evidence_id':'seoul-bulk','locator':f'{s.title}!A{i}:L{i}',
                    'schema_status':'schema_not_in_catalog','output_raw':None,'request_raw':None,
                    'description':desc,'category_raw':category,'department_raw':dept,
                    'created_raw':str(created) if created else None,'modified_raw':str(modified) if modified else None,
                    'keywords_raw':kw,'service_status_raw':state,'snapshot_label':'26년 8월',
                    'provider_note':'제공부서는 기관과 구분; 기관명을 제목에서 추정하지 않음'})
                total+=1
        w.close();self.stats['seoul']={'imported_records':total,'snapshot_label':'26년 8월',
            'all_acquired_workbook_rows_processed':True,'columns_present_in_bulk':False,
            'all_current_portal_records_confirmed':False}
        self.db.commit();print('SEOUL',total,flush=True)

    def kosis(self):
        import xlrd
        archive=zipfile.ZipFile(BytesIO(raw('kosis-bulk')))
        names=[n for n in archive.namelist() if n.endswith('.xls')]
        assert len(names)==1
        temp=DB.parent/'kosis-catalog.xls'
        with temp.open('wb') as out,archive.open(names[0]) as src:
            while chunk:=src.read(1024*1024):out.write(chunk)
        w=xlrd.open_workbook(str(temp),on_demand=True)
        counts=Counter();sheets=[]
        for si in range(w.nsheets):
            s=w.sheet_by_index(si);sheets.append({'sheet':s.name,'rows':s.nrows,'columns':s.ncols})
            for ri in range(s.nrows):
                r=s.row_values(ri)
                if len(r)<8 or not r[7] or r[7]=='통계표 아이디(TBL_ID)':
                    counts['non_table_rows']+=1;continue
                link=s.hyperlink_map.get((ri,2));url=link.url_or_path if link else None
                params=parse_qs(urlsplit(url or '').query);org=params.get('orgId',[None])[0]
                tbl=params.get('tblId',[None])[0]
                link_matches=bool(org and tbl==r[7])
                if not link_matches:
                    counts['entries_requiring_link_review']+=1
                # Source cell combines agency and survey; preserve it as-is too.
                provider=(r[3].split(',「',1)[0]).strip() or None
                self.add({'id':f'kosis-{si+1}-{ri+1}','portal_id':'kosis',
                    'dataset_key':org+'/'+tbl if link_matches else uid('unresolved',r[7],r[3]),'title':r[1].strip(),
                    'provider_id':'kosis-org-'+org if link_matches else None,'provider_name':provider,
                    'kind':'statistical_table' if link_matches else 'catalog_entry_link_review','url':url,'evidence_id':'kosis-bulk',
                    'locator':f'{names[0]}::{s.name}!A{ri+1}:H{ri+1}',
                    'output_raw':None,'request_raw':None,'schema_status':'dimensions_not_in_catalog',
                    'source_raw':r[3],'time_coverage_raw':r[4],'category_path_raw':r[5],
                    'category_code_path_raw':r[6],'source_provider_code':org,
                    'source_table_id':r[7],'linked_table_id':tbl,'link_identity_checked':link_matches,
                    'snapshot_label':s.cell_value(1,0),
                    'dimension_definitions':None,'measure_definitions':None})
                counts['imported_records']+=1
            w.unload_sheet(si);self.db.commit();print('KOSIS_SHEET',si+1,dict(counts),flush=True)
        w.release_resources()
        self.stats['kosis']={**counts,'sheets':sheets,'all_acquired_workbook_rows_processed':True,
            'columns_present_in_bulk':False,'scope':'국내 주제별통계 MT_ZTITLE',
            'all_kosis_views_collected':False}

    def finish(self):
        self.records.close();self.quarantine.close()
        self.db.executescript('''
        CREATE INDEX records_portal ON records(portal_id);
        CREATE INDEX records_provider ON records(provider_id);
        CREATE INDEX records_dataset ON records(portal_id,dataset_key);
        CREATE INDEX fields_name ON fields(name);
        CREATE INDEX fields_record ON fields(record_id);
        ''')
        self.db.commit();self.db.close();self.temp.replace(DB)
        dump(HERE/'import-report.json',{'generated_at':now(),'sources':self.stats,
            'national_all_portals_complete':False,'all_columns_complete':False,
            'raw_observation_values_collected':0,'human_approved_semantic_relations':0})
        print('DATABASE',str(DB),flush=True)

if __name__=='__main__':
    inventory=Inventory();inventory.data_go();inventory.seoul();inventory.kosis();inventory.finish()
