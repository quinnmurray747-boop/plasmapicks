"""Grades locked Top 10 plays from ESPN box scores while games are on, and saves the results.
An Over is a win once it passes the line, an Under a loss once it passes; the rest settle at the final."""
import json, os, re, sys, unicodedata, requests
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/'
TEAM={'NO':'NOP','SA':'SAS','UTAH':'UTA','GS':'GSW','NY':'NYK','WSH':'WAS'}
KEYS={'pts':['points'],'reb':['rebounds'],'ast':['assists'],'tpm':['threePointFieldGoalsMade-threePointFieldGoalsAttempted'],
      'pra':['points','rebounds','assists'],'pr':['points','rebounds'],'pa':['points','assists'],'ra':['rebounds','assists']}
tm=lambda a:TEAM.get(a,a)
def nm(s):
    s=unicodedata.normalize('NFD',str(s)).encode('ascii','ignore').decode().lower()
    s=re.sub(r'\b(jr|sr|ii|iii|iv)\b\.?','',s); return re.sub('[^a-z]','',s)
get=lambda u:requests.get(u,timeout=20).json()

def summary(hist):   # same as update.py
    days=[];W=L=P=0
    for k in sorted(hist,reverse=True):
        v=hist[k]
        if not v.get('locked'): continue
        w=sum(x.get('result')=='W' for x in v['picks']); l=sum(x.get('result')=='L' for x in v['picks']); pu=sum(x.get('result')=='P' for x in v['picks'])
        W+=w;L+=l;P+=pu; days.append({'date':k,'label':v.get('label',k),'w':w,'l':l,'p':pu,'picks':v['picks']})
    return {'w':W,'l':L,'p':P,'days':days[:14]}

def main():
    pj=os.path.join(ROOT,'data','picks.json'); hist=json.load(open(pj,encoding='utf-8')); changed=False
    for day,v in hist.items():
        if not v.get('locked') or v.get('graded') or all(x.get('result') for x in v['picks']): continue
        games=[]
        for e in get(API+'scoreboard?dates='+day.replace('-','')).get('events',[]):
            games.append({'id':e['id'],'state':e['status']['type']['state'],'teams':[tm(c['team']['abbreviation']) for c in e['competitions'][0]['competitors']]})
        box={}
        for x in v['picks']:
            if x.get('result'): continue
            g=next((g for g in games if x['t'] in g['teams']),None)
            if not g or g['state']=='pre': continue
            if g['id'] not in box: box[g['id']]=get(API+'summary?event='+g['id']).get('boxscore',{}).get('players',[])
            ath=keys=None
            for t in box[g['id']]:
                if tm(t['team']['abbreviation'])!=x['t'] or not t.get('statistics'): continue
                keys=t['statistics'][0]['keys']
                ath=next((a for a in t['statistics'][0]['athletes'] if nm(a['athlete']['displayName'])==nm(x['n'])),None)
            if not ath or ath.get('didNotPlay') or not ath.get('stats'):
                if g['state']=='post': x['result']='V'; changed=True
                continue
            a=sum(float(str(ath['stats'][keys.index(k)]).split('-')[0] or 0) for k in KEYS[x['st']] if k in keys)
            over=x['side']=='OVER'
            if g['state']=='post': x['result']='P' if a==x['line'] else ('W' if (a>x['line'])==over else 'L')
            elif a>x['line']: x['result']='W' if over else 'L'
            else: continue
            x['actual']=int(a) if a==int(a) else a; changed=True
            print(day,x['n'],x['side'],x['line'],x['st'],'->',x['result'],x['actual'])
        if all(x.get('result') for x in v['picks']): v['graded']=True; changed=True
    if not changed: print('nothing new'); return
    json.dump(hist,open(pj,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
    p=os.path.join(ROOT,'index.html'); s=open(p,encoding='utf-8').read()
    blob=json.dumps(summary(hist),ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    s,n=re.subn(r'(<script id="recdata" type="application/json">).*?(</script>)',lambda m:m.group(1)+blob+m.group(2),s,count=1,flags=re.S); assert n==1
    open(p,'w',encoding='utf-8').write(s)

if __name__=='__main__': main()
