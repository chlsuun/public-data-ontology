"""Parse a literal-only JavaScript data subset. Expressions are never evaluated."""
import re
from openapi_schema import javascript_literal

def literal_value(source,start=0):
    nodes=0
    def value(pos,depth=0):
        nonlocal nodes
        nodes+=1
        if depth>40 or nodes>100000:raise ValueError('literal_size_limit')
        while pos<len(source) and source[pos].isspace():pos+=1
        if pos>=len(source):raise ValueError('unexpected_literal_end')
        char=source[pos]
        if char in ('"',"'",'`'):return javascript_literal(source,pos)
        if char in '[{':
            array=char=='[';closing=']' if array else '}';result=[] if array else {};pos+=1
            while True:
                while pos<len(source) and source[pos].isspace():pos+=1
                if pos>=len(source):raise ValueError('unterminated_collection')
                if source[pos]==closing:return result,pos+1
                if not array:
                    if source[pos] in ('"',"'",'`'):key,pos=javascript_literal(source,pos)
                    else:
                        match=re.match(r'[A-Za-z_$][A-Za-z0-9_$]*',source[pos:])
                        if not match:raise ValueError('nonliteral_object_key')
                        key=match[0];pos+=len(key)
                    while pos<len(source) and source[pos].isspace():pos+=1
                    if source[pos:pos+1]!=':':raise ValueError('object_colon_expected')
                    if key in result:raise ValueError('duplicate_object_key')
                    pos+=1
                item,pos=value(pos,depth+1)
                if array:result.append(item)
                else:result[key]=item
                while pos<len(source) and source[pos].isspace():pos+=1
                if source[pos:pos+1]==closing:return result,pos+1
                if source[pos:pos+1]!=',':raise ValueError('expression_not_a_data_literal')
                pos+=1
        for token,item in (('true',True),('false',False),('null',None),('!0',True),('!1',False)):
            if source.startswith(token,pos):return item,pos+len(token)
        match=re.match(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?',source[pos:])
        if match:
            token=match[0];return (float(token) if any(c in token for c in '.eE') else int(token)),pos+len(token)
        raise ValueError('expression_or_identifier_not_executed')
    return value(start)
