/* PlasmaPicks live grading: checks ESPN box scores in the visitor's browser and grades each Top 10 leg
   as soon as it is decided. An Over wins the moment the stat passes the line; an Under loses the moment
   it does. Everything else is settled when the game goes final. Players who don't play are voided. */
(function(){
  var API='https://site.api.espn.com/apis/site/v2/sports/basketball/nba/';
  var TEAM={NO:'NOP',SA:'SAS',UTAH:'UTA',GS:'GSW',NY:'NYK',WSH:'WAS'};
  var KEYS={pts:['points'],reb:['rebounds'],ast:['assists'],tpm:['threePointFieldGoalsMade-threePointFieldGoalsAttempted'],
    pra:['points','rebounds','assists'],pr:['points','rebounds'],pa:['points','assists'],ra:['rebounds','assists']};
  function tm(a){return TEAM[a]||a}
  function nm(s){return String(s||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/\b(jr|sr|ii|iii|iv)\b\.?/g,'').replace(/[^a-z]/g,'')}
  function get(u){return fetch(u,{cache:'no-store'}).then(function(r){if(!r.ok)throw r.status;return r.json()})}
  function open(x){return !x.result||x.live}

  function settle(x,g){
    var side=null,ath=null;
    (g.box||[]).forEach(function(t){if(tm(t.team.abbreviation)===x.t)side=t});
    if(side&&side.statistics&&side.statistics[0]){var s=side.statistics[0];
      s.athletes.forEach(function(a){if(nm(a.athlete.displayName)===nm(x.n))ath={a:a,keys:s.keys}})}
    var played=ath&&!ath.a.didNotPlay&&ath.a.stats&&ath.a.stats.length;
    if(!played){
      if(g.state==='post'){x.result='V';delete x.live;delete x.actual;delete x.clock}
      return;
    }
    var v=0;KEYS[x.st].forEach(function(k){var i=ath.keys.indexOf(k);v+=i<0?0:parseFloat(String(ath.a.stats[i]).split('-')[0])||0});
    x.actual=v;
    var over=x.side==='OVER';
    if(g.state==='post'){x.result=v===x.line?'P':((v>x.line)===over?'W':'L');delete x.live;delete x.clock;return}
    if(v>x.line){x.result=over?'W':'L';delete x.live;delete x.clock;return}   // already decided mid-game
    x.live=true;x.result='';x.clock=g.clock;
  }

  /* days: [{date:'YYYY-MM-DD', picks:[...]}]. Picks are updated in place. Resolves to true if anything is still open. */
  function grade(days){
    var todo=days.filter(function(d){return d.picks&&d.picks.some(open)});
    return Promise.all(todo.map(function(d){
      return get(API+'scoreboard?dates='+d.date.replace(/-/g,'')).then(function(sb){
        var games=(sb.events||[]).map(function(e){return {id:e.id,state:e.status.type.state,clock:e.status.type.shortDetail,
          teams:e.competitions[0].competitors.map(function(c){return tm(c.team.abbreviation)})}});
        var need=games.filter(function(g){return g.state!=='pre'&&d.picks.some(function(x){return open(x)&&g.teams.indexOf(x.t)>=0})});
        return Promise.all(need.map(function(g){return get(API+'summary?event='+g.id).then(function(s){g.box=(s.boxscore&&s.boxscore.players)||[]}).catch(function(){})}))
          .then(function(){d.picks.forEach(function(x){if(!open(x))return;
            var g=games.filter(function(g){return g.teams.indexOf(x.t)>=0})[0];
            if(g&&g.state!=='pre'&&g.box)settle(x,g)})});
      }).catch(function(){});
    })).then(function(){return days.some(function(d){return d.picks&&d.picks.some(open)})});
  }

  /* Re-checks every minute until every leg is settled. */
  function watch(days,onUpdate){
    var stop=false;
    (function tick(){grade(days).then(function(more){onUpdate();if(more&&!stop)setTimeout(tick,60000)})})();
    return function(){stop=true};
  }
  window.PPLive={grade:grade,watch:watch};
})();
