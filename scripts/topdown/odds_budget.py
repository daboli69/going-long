"""Persistent scanner request cache and conservative monthly credit budget."""
from datetime import datetime, timezone
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import requests


def cadence(kickoffs, now):
    upcoming = [float(k)-now for k in kickoffs if k is not None and float(k)>now]
    nearest = min(upcoming, default=float('inf'))
    if nearest <= 5400: return 120
    if nearest <= 86400: return 1800
    return 21600


class OddsBudget:
    def __init__(self, path, limit=60000, clock=time.time, fetch=requests.get):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.limit=limit;self.clock=clock;self.fetch=fetch
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript('CREATE TABLE IF NOT EXISTS usage(month TEXT PRIMARY KEY, credits INTEGER); CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, at REAL, body TEXT); CREATE TABLE IF NOT EXISTS control(key TEXT PRIMARY KEY, until_at REAL);')

    def get(self,url,params,headers,timeout=35,ttl=1800,cost=3):
        now=self.clock();month=datetime.fromtimestamp(now,timezone.utc).strftime('%Y-%m')
        key=hashlib.sha256((url+json.dumps(params,sort_keys=True)).encode()).hexdigest()
        with closing(sqlite3.connect(self.path,timeout=60)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            cached=db.execute('SELECT at,body FROM cache WHERE key=?',(key,)).fetchone()
            if cached and now-cached[0]<ttl:
                response=requests.Response();response.status_code=200;response._content=cached[1].encode();return response
            pause=db.execute("SELECT until_at FROM control WHERE key='pause'").fetchone()
            if pause and pause[0]>now: raise requests.RequestException('Provider requests paused after credit or rate limit')
            used=db.execute('SELECT credits FROM usage WHERE month=?',(month,)).fetchone()
            if (used[0] if used else 0)+cost>self.limit:raise requests.RequestException('Local scanner monthly credit budget reached')
            # Reserve before transmission. Unknown failures remain charged conservatively.
            db.execute('INSERT INTO usage VALUES(?,?) ON CONFLICT(month) DO UPDATE SET credits=credits+excluded.credits',(month,cost))
            db.commit()
            response=self.fetch(url,params=params,headers=headers,timeout=timeout)
            if response.status_code in (401,403,429):
                db.execute("INSERT INTO control VALUES('pause',?) ON CONFLICT(key) DO UPDATE SET until_at=excluded.until_at",(now+(21600 if response.status_code in (401,403) else 900),))
            if response.ok:
                # Store original provider timestamps. A cache hit is not a new price observation.
                body=response.json()
                db.execute('INSERT INTO cache VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET at=excluded.at,body=excluded.body',(key,now,json.dumps(body)))
            return response

    def status(self):
        month=datetime.fromtimestamp(self.clock(),timezone.utc).strftime('%Y-%m')
        with closing(sqlite3.connect(self.path)) as db, db:
            row=db.execute('SELECT credits FROM usage WHERE month=?',(month,)).fetchone()
        return {'month':month,'reserved_credits':row[0] if row else 0,'monthly_limit':self.limit,'scope':'PC scanner only; web and scheduled builds use additional credits'}
