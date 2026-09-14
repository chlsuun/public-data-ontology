"""Read literal OpenAPI documents; no JavaScript or API operations are executed."""
import json,re
PARSER_VERSION=2

def javascript_literal(text,start):
    quote=text[start]
    if quote not in ('"',"'",'`'):raise ValueError('literal_quote_expected')
    out=[];i=start+1
    escapes={'n':'\n','r':'\r','t':'\t','b':'\b','f':'\f','v':'\v','0':'\0', '\\':'\\',"'":"'",'"':'"','`':'`','/':'/','$':'$'}
    while i<len(text):
        c=text[i]
        if c==quote:return ''.join(out),i+1
        if quote=='`' and text[i:i+2]=='${':raise ValueError('template_expression_not_executed')
        if c!='\\':out.append(c);i+=1;continue
        i+=1
        if i>=len(text):raise ValueError('unterminated_escape')
        c=text[i]
        if c in ('\n','\r'):
            i+=1
            if c=='\r' and text[i:i+1]=='\n':i+=1
            continue
        if c in ('u','x'):
            n=4 if c=='u' else 2;digits=text[i+1:i+1+n]
            if len(digits)!=n or not re.fullmatch('[0-9a-fA-F]+',digits):raise ValueError('unsupported_hex_escape')
            out.append(chr(int(digits,16)));i+=n+1
        elif c in escapes:out.append(escapes[c]);i+=1
        else:raise ValueError('unsupported_javascript_escape')
    raise ValueError('unterminated_literal')

def embedded_document(data):
    text=data.decode('utf-8-sig');m=re.search(r'\bconst\s+swaggerJson\s*=\s*',text)
    if not m:return None
    literal,end=javascript_literal(text,m.end())
    if not text[end:].lstrip().startswith(';'):raise ValueError('unexpected_literal_boundary')
    if not literal:return None
    doc=json.loads(literal)
    if not isinstance(doc,dict) or not (doc.get('swagger') or doc.get('openapi')):
        raise ValueError('openapi_version_not_observed')
    return doc

def local_ref(doc,ref):
    if not isinstance(ref,str) or not ref.startswith('#/'):
        raise ValueError('external_schema_reference_not_fetched')
    obj=doc
    for part in ref[2:].split('/'):
        part=part.replace('~1','/').replace('~0','~')
        if not isinstance(obj,dict) or part not in obj:raise ValueError('local_schema_reference_missing:'+ref)
        obj=obj[part]
    return obj

def parse_document(doc,eid):
    fields=[];parameters=[];operations=[];issues=[]
    def problem(reason,locator,operation):
        issues.append({'reason':reason,'locator':locator,'operation_id':operation['id']})
    def visit(schema,path,locator,operation,status,media,refs=(),depth=0,variant=None):
        if depth>40 or len(fields)>=50000:
            problem('schema_expansion_limit',locator,operation);return
        if not isinstance(schema,dict):
            problem('schema_not_object',locator,operation);return
        if '$ref' in schema:
            ref=schema['$ref']
            if ref in refs:problem('recursive_schema_reference',locator,operation);return
            try:resolved=local_ref(doc,ref)
            except ValueError as exc:problem(str(exc),locator,operation);return
            visit(resolved,path,ref,operation,status,media,refs+(ref,),depth+1,variant)
            return
        composite=False
        for keyword in ('allOf','oneOf','anyOf'):
            if isinstance(schema.get(keyword),list):
                composite=True
                for i,part in enumerate(schema[keyword]):
                    visit(part,path,locator+'/'+keyword+'/'+str(i),operation,status,media,refs,depth+1,(variant or '')+'/'+keyword+'/'+str(i))
        props=schema.get('properties')
        if isinstance(props,dict) and props:
            if schema.get('additionalProperties'):
                problem('additional_dynamic_properties_not_enumerated',locator,operation)
            for name,child in props.items():
                visit(child,path+[name],locator+'/properties/'+name.replace('~','~0').replace('/','~1'),operation,status,media,refs,depth+1,variant)
            return
        if schema.get('type')=='array' and isinstance(schema.get('items'),dict):
            items=schema['items']
            if items.get('$ref') or items.get('properties') or items.get('type')=='array' or any(k in items for k in ('allOf','oneOf','anyOf')):
                visit(items,path+['[]'],locator+'/items',operation,status,media,refs,depth+1,variant);return
        if composite:return
        if schema.get('type')=='object' or schema.get('additionalProperties'):
            problem('object_without_fixed_properties',locator,operation);return
        if not path:problem('scalar_response_without_named_field',locator,operation);return
        name=next((p for p in reversed(path) if p!='[]'),None)
        if name is None:return
        fields.append({'name':schema.get('title') or name,'name_en':name if name.isascii() else None,
            'description':schema.get('description'),'datatype':schema.get('type'),'unit':None,
            'role':'output_column','evidence_id':eid,'locator':'swaggerJson'+locator,
            'schema_path':path,'operation':operation,'response_status':status,'media_type':media,
            'schema_variant':variant,'definition':schema})
    for route,pathitem in (doc.get('paths') or {}).items():
        if not isinstance(pathitem,dict):continue
        for method,obj in pathitem.items():
            if method.lower() not in ('get','post','put','patch','delete','options','head','trace') or not isinstance(obj,dict):continue
            operation={'id':'openapi:'+method.upper()+':'+route,'name':obj.get('summary') or obj.get('operationId') or route,
                'method':method.upper(),'path':route,'operation_id_as_reported':obj.get('operationId')}
            start=len(fields);issue_start=len(issues);schemas=0
            for param in list(pathitem.get('parameters') or [])+list(obj.get('parameters') or []):
                parameters.append({'operation':operation,'role':'request_parameter','evidence_id':eid,'definition':param})
            if obj.get('requestBody'):parameters.append({'operation':operation,'role':'request_body','evidence_id':eid,'definition':obj['requestBody']})
            for status,response in (obj.get('responses') or {}).items():
                if not isinstance(response,dict):continue
                base='#/paths/'+route.replace('~','~0').replace('/','~1')+'/'+method+'/responses/'+str(status)
                response_refs=set()
                while isinstance(response,dict) and response.get('$ref'):
                    ref=response['$ref']
                    if ref in response_refs:
                        problem('recursive_response_reference',base,operation);response=None;break
                    response_refs.add(ref)
                    try:response=local_ref(doc,ref);base=ref
                    except ValueError as exc:problem(str(exc),base,operation);response=None;break
                if not isinstance(response,dict):continue
                if isinstance(response.get('schema'),dict):
                    schemas+=1;visit(response['schema'],[],base+'/schema',operation,str(status),None)
                for media,content in (response.get('content') or {}).items():
                    if isinstance(content,dict) and isinstance(content.get('schema'),dict):
                        schemas+=1;visit(content['schema'],[],base+'/content/'+media.replace('/','~1')+'/schema',operation,str(status),media)
            operations.append({**operation,'evidence_id':eid,'output_fields':len(fields)-start,
                'response_schemas_observed':schemas,'unresolved_schema_parts':len(issues)-issue_start,
                'status':'definition_observed' if len(fields)>start else 'definition_unresolved'})
    return {'fields':fields,'request_parameters':parameters,'operations':operations,'issues':issues,
        'specification_version':doc.get('swagger') or doc.get('openapi'),'schema_parser_version':PARSER_VERSION,
        'all_advertised_operations_have_fields':bool(operations) and all(o['output_fields'] and not o['unresolved_schema_parts'] for o in operations)}
