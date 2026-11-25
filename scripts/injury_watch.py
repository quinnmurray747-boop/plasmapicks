"""Game-day injury watch. Reads ESPN's NBA injury report, adds anyone ruled Out on today's slate to data/out.json,
and works out which locked Top 10 plays a new Out affects (the player himself, or a major teammate) in games that
haven't tipped. Prints REPICK_DROP / REPICK_SKIP lines for the workflow, which re-runs the update to replace them."""
import json, os, re, sys, datetime as dt, unicodedata, requests
from zoneinfo import ZoneInfo
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'
TEAM={'NO':'NOP','SA':'SAS','UTAH':'UTA','GS':'GSW','NY':'NYK','WSH':'WAS'}
tm=lambda a:TEAM.get(a,a)
def nm(s):
    s=unicodedata.normalize('NFD',str(s)).encode('ascii','ignore').decode().lower()
    s=re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?','',s); return re.sub('[^a-z]','',s)

def main():
    today=dt.datetime.now(ZoneInfo('America/Chicago')).date().isoformat()
    hist=json.load(open(os.path.join(ROOT,'data','picks.json'),encoding='utf-8'))
    day=hist.get(today)
    s=open(os.path.join(ROOT,'index.html'),encoding='utf-8').read()
    fb=json.loads(re.search(r'<script id="fbdata" type="application/json">(.*?)</script>',s,re.S).group(1))
    # season numbers for "major" teammates: the page data if it's today's slate
    players={}
    for row in fb.get('players','').split(';'):
        f=row.split('|')
        if len(f)>=6: players[nm(f[0])]={'n':f[0],'t':f[1],'pos':f[2],'m':float(f[4] or 0),'pts':float(f[5] or 0)}
    # who played lately: someone out for weeks is already in everyone's recent numbers, so he isn't news
    try: logs=json.loads(re.search(r'<script id="splitdata" type="application/json">(.*?)</script>',s,re.S).group(1))['logs']
    except Exception: logs={}
    def active(n,t):
        L=(logs.get(t) or {}).get('p',{})
        for k,v in L.items():
            if nm(k)==nm(n): return any(x and x[0]>0 for x in v[-5:])
        return True
    grp=lambda x:'B' if re.search('C|PF',str(x)) else ('G' if re.search('PG|SG',str(x)) else 'W')
    # game states today
    sb=requests.get(API+'scoreboard?dates='+today.replace('-',''),timeout=20).json()
    state={}
    for e in sb.get('events',[]):
        for c in e['competitions'][0]['competitors']: state[tm(c['team']['abbreviation'])]=e['status']['type']['state']
    if not state: print('no games today'); return
    # injury report
    inj=requests.get(API+'injuries',timeout=20).json()
    out=[]
    for team in inj.get('injuries',[]):
        for it in team.get('injuries',[]):
            st=str(it.get('status','')).lower(); a=it.get('athlete',{}) or {}
            name=a.get('displayName') or ''
            t=tm(((a.get('team') or {}).get('abbreviation')) or '')
            p=players.get(nm(name))
            if not t and p: t=p['t']
            if st=='out' and t in state: out.append((p['n'] if p else name,t))
    print('out on today\'s slate:',', '.join(f'{n} ({t})' for n,t in out) or 'none')
    op=os.path.join(ROOT,'data','out.json'); O=json.load(open(op)) if os.path.exists(op) else {}
    known={nm(n) for n in O.get(today,[])}
    new=[(n,t) for n,t in out if nm(n) not in known]
    if not new: print('nothing new'); return
    O[today]=O.get(today,[])+[n for n,_ in new]
    for k in [k for k in O if k<(dt.date.fromisoformat(today)-dt.timedelta(days=14)).isoformat()]: del O[k]
    json.dump(O,open(op,'w'),indent=1)
    print('newly out:',', '.join(n for n,_ in new))
    if not day or not day.get('locked'): return
    drop=[]
    for x in day['picks']:
        if x.get('result') or state.get(x['t'])!='pre': continue
        for n,t in new:
            p=players.get(nm(n))
            me=players.get(nm(x['n']),{})
            hurts=p and active(n,t) and (p['pts']>=14 or (grp(p['pos'])==grp(me.get('pos')) and p['m']>=12))
            if nm(n)==nm(x['n']) or (t==x['t'] and hurts):
                drop.append(x['n']); print(f"replace {x['n']} {x['side']} {x['line']} {x['st']}: {n} out"); break
    skip=sorted(t for t,s in state.items() if s!='pre')
    gh=os.environ.get('GITHUB_OUTPUT')
    if drop and gh:
        with open(gh,'a') as f: f.write('drop='+';'.join(drop)+'\nskip='+';'.join(skip)+'\n')

if __name__=='__main__': main()
