// Loads the built page in a headless DOM and prints the Top 5 it computes from fresh data.
const {JSDOM,VirtualConsole}=require('jsdom');const fs=require('fs');
const errs=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>errs.push(String(e.message)));
const dom=new JSDOM(fs.readFileSync(process.argv[2],'utf8'),{runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,url:'https://plasmapicks.com/',
  beforeParse(w){w.__forceTop5=true}});
let tries=0;(function wait(){const t=dom.window.__top5;
  if(t&&t.length){process.stdout.write(JSON.stringify(t));process.exit(0)}
  if(++tries>60){console.error('no Top 5 computed',errs.slice(0,3));process.stdout.write('[]');process.exit(0)}
  setTimeout(wait,500)})();
