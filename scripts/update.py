"""Daily PlasmaPicks update: stats from hoopR, lines from the odds feed, checks, then writes the page data."""
import json, re, sys, os, time, datetime as dt
from zoneinfo import ZoneInfo
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
sys.path.insert(0,HERE)
import build_stats, fetch_odds, subprocess

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
    fb['firstTip']=odds.get('first_tip')
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
    # ---- Top 10: compute with the page itself, lock before the first tip, grade past days ----
    top=json.loads(subprocess.run(['node',os.path.join(HERE,'top5.js'),p],capture_output=True,text=True,timeout=180).stdout or '[]')
    rp=os.path.join(ROOT,'data','picks.json')
    hist=json.load(open(rp)) if os.path.exists(rp) else {}
    day=hist.get(today.isoformat())
    tip=odds.get('first_tip')
    # The Top 10 is set in stone by the 11 PM CT run the night before. Later runs only refresh the board.
    lock=dt.datetime.combine(today-dt.timedelta(days=1),dt.time(23,0),ZoneInfo('America/Chicago'))
    if tip: lock=min(lock,dt.datetime.fromisoformat(tip))
    lock_iso=lock.astimezone(dt.timezone.utc).isoformat()
    fb['lockAt']=lock_iso
    started=dt.datetime.now(dt.timezone.utc)>=lock
    if top and not (day and day.get('locked')):
        if not day or not started: hist[today.isoformat()]={'label':label,'picks':top,'locked':started,'first_tip':tip,'lock_at':lock_iso}
        else: day['locked']=True
    for k,v in hist.items():
        if not v.get('locked') and (k<today.isoformat() or (k==today.isoformat() and started)): v['locked']=True
    grade(hist,d)
    json.dump(hist,open(rp,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    cur=hist.get(today.isoformat())
    fb['top5']=cur['picks'] if cur else top; fb['top5Locked']=bool(cur and cur.get('locked'))
    rec=summary(hist)
    s=open(p,encoding='utf-8').read()
    for tag,obj in (('fbdata',fb),('recdata',rec)):
        blob=json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
        s,n=re.subn(r'(<script id="%s" type="application/json">).*?(</script>)'%tag,lambda m:m.group(1)+blob+m.group(2),s,count=1,flags=re.S)
        assert n==1, tag
    open(p,'w',encoding='utf-8').write(s)
    json.dump(fb,open(os.path.join(ROOT,'data','slate.json'),'w',encoding='utf-8'),ensure_ascii=False)
    print('OK', len(odds['games']),'games | Top 10:', ', '.join(f"{x['n']} {x['side']} {x['line']} {x['st']}" for x in fb['top5']), '| record', rec['w'],'-',rec['l'],'-',rec['p'])

COLS={'pts':['points'],'reb':['rebounds'],'ast':['assists'],'tpm':['three_point_field_goals_made'],'pra':['points','rebounds','assists'],
      'pr':['points','rebounds'],'pa':['points','assists'],'ra':['rebounds','assists']}
def grade(hist,d):
    for k,v in hist.items():
        if not v.get('locked') or v.get('graded'): continue
        day=dt.date.fromisoformat(k); rows=d[d.date==day]
        if rows.empty: continue                        # box scores not in yet
        done=True
        for x in v['picks']:
            if x.get('result'): continue
            team=rows[rows.tm==x['t']]
            if team.empty: done=False; continue        # that game's box score not in yet
            me=team[(team.name==x['n'])&team.played]
            if me.empty: x['result']='V'; continue     # did not play: no action
            a=float(me[COLS[x['st']]].sum(axis=1).iloc[0]); x['actual']=int(a) if a==int(a) else a
            x['result']='P' if a==x['line'] else ('W' if (a>x['line'])==(x['side']=='OVER') else 'L')
        v['graded']=done

def summary(hist):
    days=[];W=L=P=0
    for k in sorted(hist,reverse=True):
        v=hist[k]
        if not v.get('locked'): continue
        w=sum(x.get('result')=='W' for x in v['picks']); l=sum(x.get('result')=='L' for x in v['picks']); pu=sum(x.get('result')=='P' for x in v['picks'])
        W+=w;L+=l;P+=pu; days.append({'date':k,'label':v.get('label',k),'w':w,'l':l,'p':pu,'picks':v['picks']})
    return {'w':W,'l':L,'p':P,'days':days[:14]}

if __name__=='__main__': main(sys.argv[1])
