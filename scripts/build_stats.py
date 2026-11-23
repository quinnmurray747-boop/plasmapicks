"""Season stats from hoopR box scores: players, team defense, back-to-backs, teammate logs, defense by position.
Replaces the Basketball-Reference copy-paste. Output matches the formats the page already reads."""
import pandas as pd, json, unicodedata, re, sys, os, datetime as dt
HERE=os.path.dirname(os.path.abspath(__file__))
FIX={'GS':'GSW','NO':'NOP','NY':'NYK','SA':'SAS','UTAH':'UTA','WSH':'WAS','PHO':'PHX','BRK':'BKN','CHO':'CHA'}
POSL={1:'PG',2:'SG',3:'SF',4:'PF',5:'C'}
def key(n):
    n=unicodedata.normalize('NFD',str(n)); n=''.join(c for c in n if unicodedata.category(c)!='Mn').lower()
    n=re.sub(r'[^a-z ]','',n); n=re.sub(r'\b(jr|sr|ii|iii|iv)\b','',n); return re.sub(r'\s+',' ',n).strip()

def load(box_path):
    d=pd.read_parquet(box_path)
    d=d[d.season_type.astype(str).isin(['2','regular','Regular Season'])].copy()
    d['tm']=d.team_abbreviation.replace(FIX); d['op']=d.opponent_team_abbreviation.replace(FIX)
    pos=json.load(open(os.path.join(HERE,'pos_bbref.json'),encoding='utf-8'))
    bb={key(n):n for n in pos}; bb['ronald holland']='Ron Holland'
    d['name']=[bb.get(key(n),n) for n in d.athlete_display_name]
    d['pos']=[pos.get(bb.get(key(n),''),None) for n in d.athlete_display_name]
    fb={'G':2,'F':3,'C':5,'PG':1,'SG':2,'SF':3,'PF':4}
    d['pos']=[int(p) if p==p and p else fb.get(str(a),3) for p,a in zip(d.pos,d.athlete_position_abbreviation)]
    d['played']=(~d.did_not_play.fillna(False).astype(bool))&(d.minutes.fillna(0)>0)
    for c in ['minutes','points','rebounds','assists','three_point_field_goals_made']: d[c]=d[c].fillna(0)
    d['date']=pd.to_datetime(d.game_date).dt.date
    return d

def players_str(d):
    P=d[d.played]; last=P.sort_values('date').groupby('name').tail(1).set_index('name')
    g=P.groupby('name').agg(g=('game_id','nunique'),mn=('minutes','mean'),pts=('points','mean'),reb=('rebounds','mean'),ast=('assists','mean'),tpm=('three_point_field_goals_made','mean'),pos=('pos','first'))
    g=g.sort_values('pts',ascending=False); out=[]
    for n,r in g.iterrows():
        out.append(f"{n}|{last.loc[n,'tm']}|{POSL.get(int(r.pos),'SF')}|{int(r.g)}|{r.mn:.1f}|{r.pts:.1f}|{r.reb:.1f}|{r.ast:.1f}|{r.tpm:.1f}")
    return ';'.join(out)

def teams_str(d, slate_date):
    gm=d.drop_duplicates(['game_id','tm'])[['game_id','tm','team_score','opponent_team_score','date']]
    pg=d.groupby(['game_id','tm'])[['rebounds','assists']].sum().reset_index()
    opp=pg.rename(columns={'tm':'op','rebounds':'oreb','assists':'oast'})
    gm=gm.merge(d.drop_duplicates(['game_id','tm'])[['game_id','tm','op']],on=['game_id','tm']).merge(opp,on=['game_id','op'])
    t=gm.groupby('tm').agg(ppg=('team_score','mean'),opp=('opponent_team_score','mean'),oreb=('oreb','mean'),oast=('oast','mean'),last=('date','max'))
    rk=lambda c:t[c].rank(method='min').astype(int)
    t['r1'],t['r2'],t['r3']=rk('opp'),rk('oreb'),rk('oast')
    y=slate_date-dt.timedelta(days=1)
    return ';'.join(f"{k}|{r.ppg:.1f}|{r.opp:.1f}|{r.r1}|{r.r2}|{r.r3}|{1 if r['last']==y else 0}" for k,r in t.sort_values('ppg',ascending=False).iterrows())

def splits(d):
    P=d[d.played]; logs={}
    for t,g in d.groupby('tm'):
        gm=g[['game_id','date','op','home_away']].drop_duplicates('game_id').sort_values('date'); gi={x:i for i,x in enumerate(gm.game_id)}; pl={}
        for _,r in g[g.played].iterrows():
            a=pl.setdefault(r['name'],[0]*len(gm)); a[gi[r.game_id]]=[int(round(r.minutes)),int(r.points),int(r.rebounds),int(r.assists),int(r.three_point_field_goals_made)]
        logs[t]={'g':[[x.strftime('%m-%d'),o,'@' if h=='away' else 'v'] for x,o,h in zip(gm.date,gm.op,gm.home_away)],'p':pl}
    cols=['points','rebounds','assists','three_point_field_goals_made']
    gp=P.groupby(['op','game_id','pos'])[cols].sum().reset_index(); ng=d.groupby('tm').game_id.nunique(); dvp={}
    for t in ng.index:
        x=gp[gp.op==t]; dvp[t]={p:[round(float(v),2) for v in x[x.pos==p][cols].sum()/ng[t]] for p in range(1,6)}
    return {'asof':str(d.date.max()),'games':int(d.game_id.nunique()),'logs':logs,'dvp':dvp}

if __name__=='__main__':
    d=load(sys.argv[1]); sd=dt.date.fromisoformat(sys.argv[2])
    ps=players_str(d); ts=teams_str(d,sd)
    print(len(ps.split(';')),'players |',ts[:300])
    for n in ['Tyrese Maxey','Scottie Barnes','Alperen Şengün','Kyle Kuzma']:
        print([x for x in ps.split(';') if x.startswith(n)])
