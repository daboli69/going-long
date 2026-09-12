"""Public NFL.com game-day reports. Injury designations never grant clearance."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import re
import time
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
from .model import inactive_gate, stamp, uid

ORIGIN='https://www.nfl.com'
INDEXES=[ORIGIN+'/news/',ORIGIN+'/injuries/']
METHOD='nfl_official_html_v1'
POSITIONS=r'(?:QB|RB|FB|WR|TE|OT|OG|OL|C|G|T|DT|DE|DL|NT|LB|ILB|OLB|CB|DB|S|FS|SS|K|P|LS)'


def iso(t):return datetime.fromtimestamp(t,timezone.utc).isoformat()


def nickname(name):
    n=name.upper().split()[-1] if name.strip() else ''
    return '49ERS' if n in ('NINERS','49ERS') else n


def official_url(url):
    u=urlparse(url)
    return u.scheme=='https' and u.hostname in ('www.nfl.com','nfl.com')


def fetch(url):
    """One short retry for transient failures; the collector retries next minute."""
    if not official_url(url):raise ValueError('Non-official URL')
    for attempt in range(2):
        try:
            r=requests.get(url,headers={'User-Agent':'GOING-personal-research/1.0'},timeout=(4,8))
            # Respect throttling by waiting for the next scan, not hammering it.
            if r.status_code==429:r.raise_for_status()
            r.raise_for_status()
            if not official_url(r.url):raise ValueError('Unexpected redirect')
            return r.text
        except requests.RequestException as exc:
            if attempt or getattr(exc.response,'status_code',None)==429:raise
            time.sleep(.5)


def parse_official_report(html,url,event,observed_at):
    """Require today's inactive article AND both complete, scoped team lists.

    Publication time is the article's actual metadata, not a fabricated T-90
    timestamp. Sunday articles can be published before their late-game lists.
    """
    if not official_url(url):return None
    soup=BeautifulSoup(html,'html.parser');article=None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value=json.loads(script.get_text())
            values=value if isinstance(value,list) else value.get('@graph',[value])
            article=next((v for v in values if v.get('@type')=='NewsArticle' and 'inactive' in v.get('headline','').lower()),article)
        except (ValueError,AttributeError,TypeError):continue
    if not article:return None
    published=stamp(article.get('datePublished'));kick=stamp(event.get('kickoff'))
    if published is None or kick is None or published>observed_at:return None
    local=lambda t:datetime.fromtimestamp(t,ZoneInfo('America/New_York'))
    if local(published).date()!=local(kick).date():return None
    names={nickname(event['home']):event['home'],nickname(event['away']):event['away']}
    if len(names)!=2:return None
    candidates=[]
    for block in soup.select('.story-part-rich-text-editor-wrapper'):
        headings=block.find_all(['h2','h3','h4'])
        if {nickname(h.get_text(' ',strip=True)) for h in headings}!=set(names):continue
        if len(headings)!=2:continue
        text=block.get_text(' ',strip=True)
        when=re.search(r'WHEN:\s*(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m\.?\s*ET',text,re.I)
        if not when:continue
        minutes=(int(when[1])%12+(12 if when[3].lower()=='p' else 0))*60+int(when[2] or 0)
        scheduled=local(kick).hour*60+local(kick).minute
        if abs(minutes-scheduled)>15:continue
        teams=[]
        for heading in headings:
            players=[];node=heading.find_next_sibling()
            while node and node.name not in ('h2','h3','h4'):
                if node.name in ('ul','ol'):
                    for li in node.find_all('li',recursive=False):
                        raw=li.get_text(' ',strip=True)
                        match=re.fullmatch(POSITIONS+r'\s+(.+)',raw)
                        if not match:players=[];break
                        player=re.sub(r'\s*\([^)]*\)\s*','',match[1]).strip()
                        if not re.fullmatch(r"[\w .’'\-]+",player) or len(player.split())<2:players=[];break
                        players.append(player)
                    break
                node=node.find_next_sibling()
            # A missing, empty, duplicated or unusually large list is incomplete.
            if not 1<=len(players)<=10 or len(set(players))!=len(players):break
            teams.append(dict(name=names[nickname(heading.get_text(' ',strip=True))],status='official_confirmed',inactive_players=players,published_at=article['datePublished'],verified_at=iso(observed_at),source_url=url,source_sha256=hashlib.sha256(html.encode()).hexdigest(),verification=METHOD,report_game_date=local(kick).date().isoformat()))
        if len(teams)==2:candidates.append(dict(event=event['event'],teams=teams,observed_at=iso(observed_at),method=METHOD))
    return candidates[0] if len(candidates)==1 else None


def retrieve_official_reports(events,now,get=fetch):
    """Discover current official articles, fetch concurrently, parse each matchup."""
    links=set();failures=[]
    def safe(url):
        try:return url,get(url)
        except (requests.RequestException,ValueError) as exc:
            return url,None
    with ThreadPoolExecutor(max_workers=4) as pool:
        for url,html in pool.map(safe,INDEXES):
            if html is None:failures.append('Official index unavailable');continue
            for a in BeautifulSoup(html,'html.parser').select('a[href]'):
                link=urljoin(ORIGIN,a['href'])
                if official_url(link) and '/news/' in link and 'inactive' in link.lower():links.add(link.split('#')[0])
        reports={}
        for url,html in pool.map(safe,sorted(links)[:20]):
            if html is None:failures.append('Official article unavailable');continue
            for event in events:
                try:report=parse_official_report(html,url,event,max(now,time.time()))
                except (ValueError,TypeError,KeyError,AttributeError,IndexError):
                    failures.append('Official article structure changed');continue
                if report:reports[event['event']]=report
    return reports,failures


def update_inactives(journal,events,reports,now,notify=None,retrieve=retrieve_official_reports):
    due=[e for e in events if stamp(e.get('kickoff')) is not None and 0<stamp(e['kickoff'])-now<=5400]
    if not due:return reports,dict(state='waiting_for_final_window',games=0)
    failures=[]
    try:
        found,failures=retrieve(due,now)
        now=max([now]+[stamp(r['observed_at']) for r in found.values()])
        reports.update(found)
        for report in found.values():journal.append('inactive_report',uid(report),report)
    except (requests.RequestException,ValueError,TypeError,KeyError):
        failures.append('Official report extraction unavailable')
    sent={r.get('alert_key') for r in journal.rows('notification')}
    unresolved=[];warnings=0
    for event in due:
        if inactive_gate(reports.get(event['event']),event,now):continue
        unresolved.append(event['event'])
        key=uid('inactive-feed-warning',event['event'])
        if stamp(event['kickoff'])-now<=4500 and key not in sent and notify:
            try:
                channel=notify('[WARNING] Automated Inactive Feed Failed for '+event['away']+' at '+event['home']+'. Manual override required.')
                if channel:
                    journal.append('notification',key,dict(alert_key=key,event=event['event'],channel=channel,type='inactive_feed_warning',observed_at=iso(now)))
                    sent.add(key);warnings+=1
            except Exception:
                failures.append('Inactive warning delivery failed or unknown; retry next scan')
    return reports,dict(state='verified' if not unresolved else 'awaiting_official_reports',games=len(due),verified=len(due)-len(unresolved),unresolved=unresolved,warnings_sent=warnings,failures=failures)
