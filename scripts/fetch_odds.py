"""Tonight's NBA games, spreads, totals and player props from SportsGameOdds (free tier: DraftKings, FanDuel, Caesars, ESPN BET).
The main book (DraftKings) drives the board and Top 5; the others show beside it in each player's price table."""
import os, json, time, unicodedata, re, datetime as dt, urllib.request, urllib.parse
from zoneinfo import ZoneInfo
API='https://api.sportsgameodds.com/v2/events'
CT=ZoneInfo('America/Chicago')
MAIN='draftkings'; OTHERS=['fanduel','caesars','espnbet']
NAMES={'draftkings':'DraftKings','fanduel':'FanDuel','caesars':'Caesars','espnbet':'ESPN BET'}
STATS={'points':'pts','rebounds':'reb','assists':'ast','threePointersMade':'tpm','points+rebounds+assists':'pra',
       'points+rebounds':'pr','points+assists':'pa','rebounds+assists':'ra'}
FIX={'GS':'GSW','NO':'NOP','NY':'NYK','SA':'SAS','UTAH':'UTA','WSH':'WAS','PHO':'PHX','BRK':'BKN','CHO':'CHA'}

def key(n):
    n=unicodedata.normalize('NFD',str(n)); n=''.join(c for c in n if unicodedata.category(c)!='Mn').lower()
    n=re.sub(r'[^a-z ]','',n); n=re.sub(r'\b(jr|sr|ii|iii|iv)\b','',n); return re.sub(r'\s+',' ',n).strip()
ALIAS={'herb jones':'herbert jones','deuce mcbride':'miles mcbride','cam johnson':'cameron johnson','ronald holland':'ron holland'}

def get(params):
    out=[]; cursor=None
    for _ in range(10):
        q=dict(params); 
        if cursor: q['cursor']=cursor
        req=urllib.request.Request(API+'?'+urllib.parse.urlencode(q),headers={'x-api-key':os.environ['ODDS_API_KEY']})
        with urllib.request.urlopen(req,timeout=60) as r: j=json.load(r)
        if not j.get('success',True): raise RuntimeError(j)
        out+=j.get('data',[]); cursor=j.get('nextCursor')
        if not cursor: break
        time.sleep(7)   # free tier: 10 requests a minute
    return out

def dec(american):
    a=float(american); return round(1+a/100,3) if a>0 else round(1+100/abs(a),3)

def slate(day, known_players):
    start=dt.datetime.combine(day,dt.time(6),CT); end=start+dt.timedelta(hours=24)
    evs=get({'leagueID':'NBA','oddsAvailable':'true','limit':50,
             'startsAfter':start.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'startsBefore':end.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})
    try:
        y=get({'leagueID':'NBA','limit':50,'startsAfter':(start-dt.timedelta(days=1)).astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
               'startsBefore':start.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')})
        yday={FIX.get(t['names']['short'],t['names']['short']) for e in y if not e['status'].get('cancelled') for t in (e['teams']['home'],e['teams']['away'])}
    except Exception as ex:
        print('yesterday lookup failed, back-to-backs from box scores only:',ex); yday=set()
    kn={key(n):n for n in known_players}
    games=[]; books={b:{} for b in [MAIN]+OTHERS}; unmatched=set()
    for e in sorted(evs,key=lambda x:x['status']['startsAt']):
        if e['status'].get('cancelled'): continue
        H=FIX.get(e['teams']['home']['names']['short'],e['teams']['home']['names']['short'])
        A=FIX.get(e['teams']['away']['names']['short'],e['teams']['away']['names']['short'])
        tid={e['teams']['home']['teamID']:H,e['teams']['away']['teamID']:A}
        o=e.get('odds',{})
        def pick(oid,field):
            x=o.get(oid) or {}; bk=(x.get('byBookmaker') or {}).get(MAIN) or {}
            v=bk.get(field) if bk.get('available',True) else None
            if v in (None,''): v=x.get('book'+field[0].upper()+field[1:])
            return float(v) if v not in (None,'') else None
        spread=pick('points-home-game-sp-home','spread'); total=pick('points-all-game-ou-over','overUnder')
        t=dt.datetime.fromisoformat(e['status']['startsAt'].replace('Z','+00:00')).astimezone(CT)
        games.append([A,H,t.strftime('%a %-I:%M%p CT').replace('AM','am').replace('PM','pm'),spread,total,''])
        for oid,x in o.items():
            pid=x.get('playerID')
            if not pid or x.get('periodID')!='game' or x.get('betTypeID')!='ou' or x.get('sideID')!='over': continue
            st=STATS.get(x.get('statID'))
            if not st: continue
            under=o.get(x.get('opposingOddID') or '') or {}
            pl=(e.get('players') or {}).get(pid) or {}
            k=key(pl.get('name','')); k=ALIAS.get(k,k); name=kn.get(k)
            if not name: unmatched.add(pl.get('name',pid)); continue
            for b in books:
                ob=(x.get('byBookmaker') or {}).get(b) or {}; ub=(under.get('byBookmaker') or {}).get(b) or {}
                if not (ob.get('available',True) and ub.get('available',True)): continue
                if not (ob.get('odds') and ub.get('odds') and ob.get('overUnder')) or ob.get('overUnder')!=ub.get('overUnder'): continue
                books[b].setdefault(st,[]).append(f"{name}|{float(ob['overUnder']):g}|{dec(ob['odds'])}|{dec(ub['odds'])}")
    main={st:';'.join(v) for st,v in books[MAIN].items()}; main['book']=NAMES[MAIN]
    others={NAMES[b]:{st:';'.join(v) for st,v in books[b].items()} for b in OTHERS if books[b]}
    if unmatched: print('names not matched to stats (skipped):',', '.join(sorted(unmatched)))
    return {'games':games,'underdog':main,'books':others,'out':[],'yesterday':sorted(yday)}
