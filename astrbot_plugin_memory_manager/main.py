import re, sqlite3
from datetime import datetime
from pathlib import Path
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest
from astrbot.api.star import Context, Star, register

DATA_DIR = Path('/AstrBot/data/plugin_data/astrbot_plugin_memory_manager')
DB_FILE = DATA_DIR / 'memory_manager.db'

def now(): return datetime.now().isoformat(timespec='seconds')
def tokens(t):
    cs=[c for c in (t or '').lower() if not c.isspace()]
    return set(cs) | set(''.join(cs[i:i+2]) for i in range(max(0, len(cs)-1)))
def sim(a,b):
    x,y=tokens(a),tokens(b)
    return len(x&y)/len(x|y) if x and y else 0.0

@register('astrbot_plugin_memory_manager','沈砚清','综合记忆管理系统','1.0.0')
class MemoryManagerPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DB_FILE) as db:
            db.execute('CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, category TEXT, content TEXT, tags TEXT DEFAULT "", importance INTEGER DEFAULT 5, status TEXT DEFAULT "active", layer TEXT DEFAULT "event", resolved INTEGER DEFAULT 0)')
            db.commit()
    def conn(self): return sqlite3.connect(DB_FILE)
    def save(self, content, category='daily', tags='', importance=5):
        with self.conn() as db:
            db.execute('INSERT INTO memories(created_at,category,content,tags,importance) VALUES(?,?,?,?,?)',(now(),category,content,tags,int(importance)))
            db.commit(); mid=db.execute('SELECT last_insert_rowid()').fetchone()[0]
        return f'已保存记忆 #{mid}'
    def surface(self, q='', limit=3):
        with self.conn() as db:
            rows=db.execute('SELECT id,content,category,importance,layer FROM memories WHERE status="active" AND layer!="archive" ORDER BY importance DESC,id DESC LIMIT 100').fetchall()
        top=sorted([(100 if r[4]=='core' else 0)+(r[3] or 5)+sim(q,r[1])*10, sim(q,r[1]), r] for r in rows, reverse=True, key=lambda x:x[0])[:int(limit)]
        return '\n'.join(f'- #{r[0]} [{r[2]}][{r[4]}] sim:{s:.2f} {r[1]}' for _,s,r in top)
    def query(self, category=None, keyword=None, limit=10):
        sql='SELECT id,category,content,tags,layer FROM memories WHERE status="active"'; args=[]
        if category: sql+=' AND category=?'; args.append(category)
        if keyword: sql+=' AND content LIKE ?'; args.append(f'%{keyword}%')
        sql+=' ORDER BY id DESC LIMIT ?'; args.append(int(limit))
        with self.conn() as db: rows=db.execute(sql,args).fetchall()
        return '\n'.join(f'#{r[0]} [{r[1]}][{r[4]}] {r[2]} tags:{r[3]}' for r in rows) or '没有找到记忆。'
    @filter.on_llm_request()
    async def inject_memory(self,event:AstrMessageEvent,req:ProviderRequest):
        block=self.surface(getattr(event,'message_str','') or '',3)
        if block: req.system_prompt=(req.system_prompt or '')+'\n\n## 语义关联记忆（自动浮现）\n'+block+'\n'
    @filter.command('memory', alias={'/memory'})
    async def memory_command(self,event:AstrMessageEvent):
        raw=re.sub(r'^/?memory\s*','',(getattr(event,'message_str','') or '').strip()).strip(); parts=raw.split(maxsplit=2)
        if not parts: yield event.plain_result('用法：/memory save/query/search/semantic/surface/count/core/resolve'); return
        a=parts[0]
        if a=='save' and len(parts)>=3: yield event.plain_result(self.save(parts[2],parts[1])); return
        if a=='query': yield event.plain_result(self.query(parts[1] if len(parts)>1 else None)); return
        if a=='search' and len(parts)>1: yield event.plain_result(self.query(keyword=raw.split(maxsplit=1)[1])); return
        if a=='semantic' and len(parts)>1: yield event.plain_result(self.surface(raw.split(maxsplit=1)[1],10) or '没有找到记忆。'); return
        if a=='surface': yield event.plain_result(self.surface('',10) or '暂无记忆。'); return
        if a=='count':
            with self.conn() as db: n=db.execute('SELECT COUNT(*) FROM memories WHERE status="active"').fetchone()[0]
            yield event.plain_result(f'当前 active 记忆：{n} 条'); return
        if a=='core' and len(parts)>1:
            with self.conn() as db: db.execute('UPDATE memories SET layer="core" WHERE id=?',(int(parts[1]),)); db.commit()
            yield event.plain_result(f'#{parts[1]} 已标记为 core。'); return
        if a=='resolve' and len(parts)>1:
            with self.conn() as db: db.execute('UPDATE memories SET resolved=1 WHERE id=?',(int(parts[1]),)); db.commit()
            yield event.plain_result(f'#{parts[1]} 已标记为已解决。'); return
    @filter.llm_tool()
    async def memory_save(self,event:AstrMessageEvent,content:str,category:str='daily',tags:str='',importance:int=5)->str:
        return self.save(content,category,tags,importance)
    @filter.llm_tool()
    async def memory_query(self,event:AstrMessageEvent,category:str='',keyword:str='',limit:int=10)->str:
        return self.query(category or None,keyword or None,limit)
    @filter.llm_tool()
    async def memory_surface(self,event:AstrMessageEvent,limit:int=3)->str:
        return self.surface('',limit)
