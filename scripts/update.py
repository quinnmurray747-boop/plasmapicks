"""Daily PlasmaPicks update: stats from hoopR, lines from the odds feed, checks, then writes the page data."""
import json, re, sys, os, time, datetime as dt
from zoneinfo import ZoneInfo
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE)
import build_stats, fetch_odds

def main(box_path):
    now=dt.datetime.now(ZoneInfo('America/Chicago')); today=dt.date.fromisoformat(os.environ['SLATE_DATE']) if os.environ.get('SLATE_DATE') else (now.date()+dt.timedelta(days=1) if now.hour>=21 else now.date())  # late at night, build tomorrow's slate
    d=build_stats.load(box_path)
    players=build_stats.players_str(d); teams=build_stats.teams_str(d,today); sp=build_stats.splits(d)
    known={p.split('|')[0] for p in players.split(';')}
    odds=fetch_odds.slate(today, known)          # games, lines per book, injuries
    problems=[]
    if not odds['games']: problems.append('no games found for today')
    for g in odds['games']:
        if g[3] is None or g[4] is None: problems.append(f'missing spread/total for {g[0]}@{g[1]}')
    if problems:
        print('NOT PUBLISHED:', '; '.join(problems)); sys.exit(1)
    stamp=now.strftime('%b. %-d, %-I:%M %p CT')
    label=dt.datetime.combine(today,dt.time()).strftime('%A, %b. %-d')
    fb={'date':today.isoformat(),'label':label,'updated':stamp,'games':odds['games'],
        'teams':teams,'players':players,
        'lines':dict({'date':today.isoformat(),'updated':stamp,'source':'Odds feed','in':'','out':';'.join(odds['out']),'q':'','ts':int(time.time())},**odds['underdog']),
        'books':odds['books'],'h2h':''}
    yd=set(odds.get('yesterday',[]))
    teams=';'.join(t[:-1]+'1' if t.split('|')[0] in yd else t for t in teams.split(';')); fb['teams']=teams
    b2b={t.split('|')[0] for t in teams.split(';') if t.endswith('|1')}
    for g in fb['games']: g[5]=' '.join(f'{t}: playing on the second night of a back-to-back.' for t in (g[0],g[1]) if t in b2b)
    os.makedirs(os.path.join(ROOT,'data'),exist_ok=True)
    json.dump(fb,open(os.path.join(ROOT,'data','slate.json'),'w',encoding='utf-8'),ensure_ascii=False)
    json.dump(sp,open(os.path.join(ROOT,'data','splits.json'),'w',encoding='utf-8'),ensure_ascii=False)
    p=os.path.join(ROOT,'index.html'); s=open(p,encoding='utf-8').read()
    for tag,obj in (('fbdata',fb),('splitdata',sp)):
        blob=json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
        s,n=re.subn(r'(<script id="%s" type="application/json">).*?(</script>)'%tag,lambda m:m.group(1)+blob+m.group(2),s,count=1,flags=re.S)
        assert n==1, tag
    open(p,'w',encoding='utf-8').write(s)
    print('OK', len(odds['games']),'games')

if __name__=='__main__': main(sys.argv[1])
