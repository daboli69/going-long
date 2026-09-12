"""Durable local journal; optional Supabase mirror. All rows immutable by id."""
import json
import os
import sqlite3
import requests
from datetime import datetime,timezone
from pathlib import Path


class Journal:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS journal(id TEXT PRIMARY KEY, kind TEXT NOT NULL, observed_at TEXT NOT NULL, payload TEXT NOT NULL, synced INTEGER DEFAULT 0)')
        self.db.execute('CREATE INDEX IF NOT EXISTS journal_kind_time ON journal(kind,observed_at)')
        self.db.execute('CREATE INDEX IF NOT EXISTS journal_delivery ON journal(synced,observed_at)')
    def append(self,kind,id,payload):
        at=payload.get('observed_at') or datetime.now(timezone.utc).isoformat()
        self.db.execute('INSERT OR IGNORE INTO journal(id,kind,observed_at,payload) VALUES(?,?,?,?)',(id,kind,at,json.dumps(payload,allow_nan=False)));self.db.commit()
    def rows(self,kind):
        return [json.loads(r[0]) for r in self.db.execute('SELECT payload FROM journal WHERE kind=? ORDER BY observed_at',(kind,))]
    def sync(self):
        url,key,owner=(os.getenv(k) for k in ('SUPABASE_URL','SUPABASE_SERVICE_ROLE_KEY','GOING_OWNER_ID'))
        if not all((url,key,owner)):return {'status':'not_configured'}
        # Raw polling quotes stay on disk; mirror decisions and their evidence,
        # rather than exhausting a small cloud database with unchanged markets.
        quote_filter='' if os.getenv('SUPABASE_SYNC_RAW_QUOTES')=='1' else " AND kind!='quote'"
        records=self.db.execute("SELECT id,kind,observed_at,payload FROM journal WHERE synced=0"+quote_filter+" ORDER BY CASE WHEN kind='run' THEN 0 WHEN kind='notification' THEN 1 WHEN kind='quote' THEN 3 ELSE 2 END, observed_at DESC LIMIT 1000").fetchall()
        if not records:return {'status':'up_to_date'}
        r=requests.post(url.rstrip('/')+'/rest/v1/market_journal?on_conflict=id',headers={'apikey':key,'Authorization':'Bearer '+key,'Prefer':'resolution=ignore-duplicates','Content-Type':'application/json'},json=[{'id':id,'owner_id':owner,'kind':kind,'observed_at':at,'payload':json.loads(body)} for id,kind,at,body in records],timeout=30)
        r.raise_for_status()
        self.db.executemany('UPDATE journal SET synced=1 WHERE id=?',[(r[0],) for r in records]);self.db.commit()
        return {'status':'synced','rows':len(records)}
