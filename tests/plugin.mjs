// SPDX-License-Identifier: AGPL-3.0-only
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const root = new URL("../", import.meta.url);
const plugin = readFileSync(new URL("dist/zxaBinbina.sptl.js", root), "utf8");
const events = {}, updates = {}, sent = [], actions = [], timers = [];
let commands = [], needLines = false, fail = false, registered, responseLocale = "en-US";
let now = {track: {id:"one", source:"local", title:"Song", artists:[{name:"Singer"}], duration:10000},
           state:"paused", position:2000, speed:1, lyricOffsetMs:100, sendTimestamp:12345};
let status = {durationMs:10000, volume:0.5, repeat:"list", shuffle:"off", currentIndex:0};
let queueFailure = false;
let queueGate = null, queueQueries = 0;
const queueTracks = Array.from({length:80}, (_, i) => ({...now.track, id:String(i), title:"Song " + i}));
const splayer = {
  locale:"en-US",
  getSetting: () => undefined,
  onSettingChange: (key, callback) => updates[key] = callback,
  register: (data) => registered = {...registered, ...data},
  log: {warn: () => {}},
  player: {
    on: (event, handler) => events[event] = handler,
    getNowPlaying: async () => now,
    getStatus: async () => status,
    setPlayMode: async mode => { status = {...status, ...mode}; actions.push(["mode", {...mode}]); },
    getQueue: async ({offset, limit}) => {
      queueQueries++;
      if (queueGate) await queueGate;
      if (queueFailure) throw new Error("temporarily unavailable");
      return {tracks:queueTracks.slice(offset,offset+limit), total:queueTracks.length, currentIndex:status.currentIndex, offset};
    },
    playTrack: async track => actions.push(["track", track.id]),
    prev: () => actions.push("prev"), next: () => actions.push("next"),
    play: () => actions.push("play"), pause: () => actions.push("pause"),
    seek: value => actions.push(["seek", value]), setVolume: value => actions.push(["volume",value])
  },
  request: async (url, options) => {
    assert.equal(url, "http://127.0.0.1:43827/exchange");
    assert.equal(options.headers["X-SPTL-Client"], "plugin");
    sent.push(JSON.parse(options.body));
    if (fail) throw new Error("lost response");
    return {status:200, body:{protocol:1, locale:responseLocale, needLines, commands}};
  }
};
const context = vm.createContext({splayer, setInterval: callback => timers.push(callback), Date, Math, Set});
vm.runInContext(plugin, context);
const flush = async () => { for(let i=0;i<12;i++) await new Promise(resolve=>setImmediate(resolve)); };
await flush();
assert.equal(registered.settings.length, 0, "appearance settings belong to Plasma");
assert.equal(Object.keys(updates).length, 0, "no SP settings subscriptions");
assert.equal(sent[0].playback.timestamp, 12345);
assert.equal(sent[0].playback.offset, 100);
assert.equal(sent[0].settings, undefined, "SP must not overwrite shared Plasma settings");
events.trackChange({track:now.track});
await flush();
events.lyricChange({lines:[{words:[{word:"Hello",startTime:1000,endTime:3000}],startTime:1000,romanLyric:"Roman",translatedLyric:"翻译"}]});
await flush();
assert.equal(sent.at(-1).lines[0].romanLyric, "Roman");
timers[0](); await flush();
assert.equal(sent.at(-1).lines, undefined, "unchanged lyrics should not be retransmitted");
commands = [{id:1,action:"next"},{id:2,action:"volume",value:0.05}];
timers[0](); await flush();
assert.deepEqual(actions, ["next",["volume",0.55]]);
timers[0](); await flush();
assert.equal(actions.length, 2, "duplicate delivery must not repeat playback commands");
assert.deepEqual(sent.at(-1).ack, [1,2]);
commands = [];
needLines = true;
timers[0](); await flush();
needLines = false;
timers[0](); await flush();
assert.equal(sent.at(-1).lines.length, 1, "bridge restart must recover complete lyrics");
fail = true; timers[0](); await flush();
fail = false; timers[0](); await flush();
assert.equal(sent.at(-1).lines.length, 1, "retry after network failure includes lyrics");

responseLocale = "zh-CN"; timers[0](); await flush();
assert.equal(registered.settings.length, 0);
assert.equal(registered.events.length, 4, "relocalizing settings retains event registration");

commands = [{id:3,action:"mode",value:"one"}];
timers[0](); await flush(); timers[0](); await flush();
assert.equal(sent.at(-1).playback.repeat, "one");
assert.equal(sent.at(-1).playback.shuffle, "off");
assert.equal(actions.filter(action => action[0] === "mode").length, 1, "repeated delivery must not repeat mode changes");
commands = [{id:4,action:"mode",value:"shuffle"}];
timers[0](); await flush(); timers[0](); await flush();
assert.equal(sent.at(-1).playback.repeat, "list");
assert.equal(sent.at(-1).playback.shuffle, "on");
status.currentIndex = 70;
commands = [{id:5,action:"queue",value:-1}];
timers[0](); await flush(); timers[0](); await flush();
assert.equal(sent.at(-1).queue.offset, 50, "initial page should contain the current track");
assert.equal(sent.at(-1).queue.tracks.length, 30);
assert.equal(sent.at(-1).queue.requestId, 5);
commands = [{id:6,action:"queuePlay",value:{index:70,id:"70",source:"local",path:""}}];
timers[0](); await flush();
assert.deepEqual(actions.at(-1), ["track","70"]);
queueTracks[70] = {...queueTracks[70],id:"replacement"};
commands = [{id:7,action:"queuePlay",value:{index:70,id:"70",source:"local",path:""}}];
timers[0](); await flush(); timers[0](); await flush();
assert.equal(sent.at(-1).commandError, "queue_changed", "stale clicks must not play another song");
assert.equal(actions.filter(action => action[0] === "track").length, 1);
queueFailure = true;
commands = [{id:8,action:"queue",value:0}];
timers[0](); await flush(); timers[0](); await flush();
assert.equal(sent.at(-1).queue.requestId, 8);
assert.equal(sent.at(-1).queue.error, "unavailable");
assert.ok(sent.at(-1).ack.includes(8), "failed queue queries must be acknowledged without disconnecting playback");
queueFailure = false;
commands = [{id:9,action:"queue",value:0}];
timers[0](); await flush(); timers[0](); await flush();
assert.equal(sent.at(-1).queue.error, "");
assert.equal(sent.at(-1).commandError, "");
assert.equal(sent.at(-1).queue.tracks.length, 50);
queueTracks.splice(3);
commands = [{id:10,action:"queue",value:50}];
timers[0](); await flush(); timers[0](); await flush();
assert.equal(sent.at(-1).queue.offset, 0, "a shortened playlist must return to an existing page");
assert.equal(sent.at(-1).queue.tracks.length, 3);
let releaseQueue;
queueGate = new Promise(resolve => releaseQueue = resolve);
commands = [{id:12,action:"queue",value:0}];
const queriesBefore = queueQueries;
timers[0](); await flush();
const sendsBefore = sent.length;
timers[0](); await flush(); timers[0](); await flush();
assert.equal(sent.length, sendsBefore + 2, "slow queue IPC must not block playback exchanges");
assert.equal(queueQueries, queriesBefore + 1, "a pending query must not execute twice");
assert.ok(!sent.at(-1).ack.includes(12), "a pending query cannot be acknowledged yet");
const playbackBefore = actions.length;
commands = [{id:12,action:"queue",value:0}, {id:13,action:"toggle",value:"playing"},
            {id:14,action:"mode",value:"one"}, {id:15,action:"setVolume",value:.6}];
timers[0](); await flush(); timers[0](); await flush();
assert.ok(actions.slice(playbackBefore).some(action => action === "play"), "a slow queue query must not block playback buttons");
assert.ok(actions.slice(playbackBefore).some(action => action[0] === "mode"), "playback mode must have an independent execution lane");
assert.ok(actions.slice(playbackBefore).some(action => action[0] === "volume"), "volume must not wait for slow navigation or queue reads");
assert.ok(sent.at(-1).results.some(result => result.id === 13 && result.ok), "button outcomes must identify the completed request");
assert.ok(!sent.at(-1).ack.includes(12), "the unfinished query remains unacknowledged while other buttons complete");
releaseQueue(); queueGate = null; await flush();
timers[0](); await flush();
assert.equal(sent.at(-1).queue.requestId, 12);
assert.ok(sent.at(-1).ack.includes(12));
const seeksBefore = actions.filter(action => action[0] === "seek").length;
commands = [{id:16, action:"seek", value:4000, targetTrack:{id:"old-track",source:"local",path:""}}];
timers[0](); await flush(); timers[0](); await flush();
assert.equal(actions.filter(action => action[0] === "seek").length, seeksBefore, "a delayed seek must not move a different song");
assert.ok(sent.at(-1).results.some(result => result.id === 16 && !result.ok));
const setMode = splayer.player.setPlayMode;
splayer.player.setPlayMode = async () => { throw null; };
commands = [{id:17, action:"mode", value:"one"}];
timers[0](); await flush(); timers[0](); await flush();
assert.ok(sent.at(-1).results.some(result => result.id === 17 && !result.ok), "malformed host errors must settle the failed request");
splayer.player.setPlayMode = setMode;
commands = [{id:18, action:"mode", value:"list"}];
timers[0](); await flush(); timers[0](); await flush();
assert.ok(sent.at(-1).results.some(result => result.id === 18 && result.ok), "a failed operation must not block the next request in its lane");
let legacyTimer;
commands = [{id:11,action:"queue",value:0}];
vm.runInNewContext(plugin, {splayer:{...splayer, player:{...splayer.player, getQueue:undefined}},
  setInterval: callback => legacyTimer = callback, Date, Math, Set});
await flush(); legacyTimer(); await flush();
assert.equal(sent.at(-1).queue.available, false, "API 4 hosts retain playback without a queue API");
assert.equal(sent.at(-1).commandError, "queue_unavailable");
commands = [];

const logicSource = readFileSync(new URL("plasmoid/contents/ui/Logic.js", root),"utf8").replace(".pragma library","");
const logic = vm.createContext({});
vm.runInContext(logicSource,logic);
const line = {text:"Original",translatedLyric:"Translation",romanLyric:"",startTime:0,timed:true,wordTimed:false,isBG:false,words:[]};
const next = {...line,text:"Next",startTime:2000};
const settings = {lyricMode:"double",auxiliary:"translation",singlePreferAux:false};
assert.equal(logic.display([line,next],0,now.track,settings,false,"Idle","Unknown").secondary,"Translation");
settings.auxiliary="romanization";
assert.equal(logic.display([line,next],0,now.track,settings,false,"Idle","Unknown").secondary,"Next");
settings.lyricMode="single"; settings.singlePreferAux=true;
assert.equal(logic.display([line,next],0,now.track,settings,false,"Idle","Unknown").primary,"Original");
settings.auxiliary="translation";
assert.equal(logic.display([line,next],0,now.track,settings,false,"Idle","Unknown").primary,"Translation");
assert.equal(logic.currentIndex([line,{...next,isBG:true},next],2500),2);
assert.equal(logic.wordProgress({startTime:100,endTime:200},150),0.5);
assert.equal(logic.width("auto",320,420,900,42,88,24),420);
const romanLine = {...line, romanLyric:"Hello world", wordTimed:true,
    words:[{word:"A",romanWord:"Hello ",startTime:0,endTime:100}, {word:"B",romanWord:"world",startTime:100,endTime:200}]};
assert.equal(logic.auxiliaryWords(romanLine,"romanization").length,2);
assert.equal(logic.auxiliaryWords(romanLine,"translation").length,0);
settings.lyricMode="double"; settings.auxiliary="romanization";
assert.equal(logic.display([romanLine],0,now.track,settings,false,"Idle","Unknown").secondaryWords.length,2);
console.log("Plugin sandbox and lyric-layout acceptance checks passed");

// Exercise official authenticated APIs and a multi-batch liked playlist.
const likedTracks = Array.from({length:623}, (_, i) => ({id:i+1, name:"Liked " + i, ar:[{id:1,name:"Singer"}], al:{id:2,name:"Album",picUrl:"https://example.com/cover.jpg"},dt:180000}));
let likedTimer, likedCommands = [], apiFailure = "", likedIds = likedTracks.map(track => track.id);
const likedSent = [], likedActions = [], likedQueue = [];
const likedPlayer = {...splayer.player,
  getNowPlaying: async () => now,
  setVolume: value => likedActions.push(["volume", value]),
  setPlayMode: async mode => likedActions.push(["mode", mode]),
  playTrack: async track => { likedActions.push(["track", track]); likedQueue.splice(0, likedQueue.length, track); },
  addToQueue: async (tracks, position) => {
    assert.ok(tracks.length <= 50); assert.equal(position,"next");
    likedQueue.splice(1, 0, ...tracks);
  },
  play: () => likedActions.push("play")
};
const likedHost = {...splayer, player:likedPlayer,
  api:{call:async (platform,name,params) => {
    assert.equal(platform,"netease");
    if (apiFailure === "login") return {ok:true,body:{code:301}};
    const body = name === "login_status" ? {data:{profile:{userId:42}}} :
      name === "likelist" ? {code:200,ids:likedIds} :
      {code:200,songs:params.ids.split(",").map(id => likedTracks.find(track => String(track.id) === id))};
    return {ok:true,status:200,body};
  }},
  request:async (_url,options) => { likedSent.push(JSON.parse(options.body)); return {status:200,body:{protocol:1,commands:likedCommands}}; }
};
vm.runInNewContext(plugin,{splayer:likedHost,setInterval:callback => likedTimer=callback,Date,Math,Set,Map});
await flush();
assert.equal(likedSent.at(-1).startAvailable,true);
likedCommands=[{id:100,action:"startLiked"}]; likedTimer(); await flush(); likedTimer(); await flush();
assert.equal(likedQueue.length,623,"all liked tracks are queued, across the 50-track host limit");
assert.deepEqual(likedQueue.map(track => track.id),likedTracks.map(track => String(track.id)),"batch insertion preserves the liked playlist order");
assert.equal(likedQueue[0].source,"netease");
assert.equal(likedQueue[0].duration,180000);
assert.equal(likedActions.filter(action => action === "play").length,1,"retried start requests do not restart playback");
assert.ok(likedSent.at(-1).ack.includes(100));
likedCommands=[{id:101,action:"setVolume",value:0},{id:102,action:"setVolume",value:1}];
likedTimer(); await flush();
assert.deepEqual(likedActions.slice(-2),[["volume",0],["volume",1]],"absolute volume can mute and restore full volume");
apiFailure="login"; likedCommands=[{id:103,action:"startLiked"}];
likedTimer(); await flush(); likedTimer(); await flush();
assert.equal(likedSent.at(-1).commandError,"login_required");
apiFailure=""; likedIds=[]; likedCommands=[{id:104,action:"startLiked"}];
likedTimer(); await flush(); likedTimer(); await flush();
assert.equal(likedSent.at(-1).commandError,"liked_empty");
console.log("Liked playback, queue ordering, authentication errors and absolute volume checks passed");

let fmClock = Date.now(), fmTimer, fmCommands = [], fmGate = null, fmFailure = false, trackAfterFeedback = null;
let fmNow = {track:{id:"fm-song",source:"netease",path:"",title:"FM",artists:[],duration:120000},state:"playing",position:25000};
let fmQueueTracks = [], fmQueueIndex = -1;
const fmSent = [], fmFeedback = [], fmActions = [];
class FMDate extends Date { static now() { return fmClock; } }
const fmHost = {...splayer,
  player:{...splayer.player,
    getNowPlaying:async()=>fmNow,
    getStatus:async()=>({...status,currentIndex:fmQueueIndex}),
    getQueue:async({offset})=>{
      if(fmGate) await fmGate;
      if(fmFailure) throw new Error("IPC unavailable");
      return {tracks:fmQueueTracks.slice(offset,offset+1),total:fmQueueTracks.length,currentIndex:fmQueueIndex,offset};
    },
    next:()=>fmActions.push("next")
  },
  api:{call:async(platform,name,params)=>{
    assert.equal(platform,"netease");assert.equal(name,"fm_trash");
    fmFeedback.push({...params});
    if (trackAfterFeedback) { fmNow={...fmNow,track:trackAfterFeedback}; trackAfterFeedback=null; }
    return {ok:true,body:{code:200}};
  }},
  request:async(_url,options)=>{fmSent.push(JSON.parse(options.body));return {status:200,body:{protocol:1,commands:fmCommands}};}
};
vm.runInNewContext(plugin,{splayer:fmHost,setInterval:callback=>fmTimer=callback,Date:FMDate,Math,Set,Map});
const fmTick=async()=>{fmClock+=1100;fmTimer();await flush();};
await flush();await fmTick();
assert.equal(fmSent.at(-1).fmActive,true,"native FM songs are outside the normal queue");
assert.equal(fmSent.at(-1).fmAvailable,true);
fmCommands=[{id:501,action:"dislike",value:{id:"fm-song",source:"netease",path:""}}];
await fmTick();await fmTick();
assert.deepEqual(fmFeedback,[{id:"fm-song",time:25}]);
assert.deepEqual(fmActions,["next"],"dislike submits feedback before advancing native FM");
assert.ok(fmSent.at(-1).ack.includes(501));
fmNow={...fmNow,track:{...fmNow.track,id:"new-fm-song"}};
fmCommands=[{id:502,action:"dislike",value:{id:"fm-song",source:"netease",path:""}}];
await fmTick();await fmTick();
assert.equal(fmSent.at(-1).commandError,"fm_changed");
assert.equal(fmFeedback.length,1,"stale clicks never dislike a different song");
trackAfterFeedback={...fmNow.track,id:"changed-during-feedback"};
fmCommands=[{id:503,action:"dislike",value:{id:"new-fm-song",source:"netease",path:""}}];
await fmTick();await fmTick();
assert.equal(fmFeedback.length,2);
assert.deepEqual(fmActions,["next"],"feedback completion must not skip a newly selected song");
fmCommands=[];fmQueueTracks=[fmNow.track];fmQueueIndex=0;
await fmTick();await fmTick();
assert.equal(fmSent.at(-1).fmActive,false,"regular queued online songs retain Previous and playback mode");
let releaseFm;
fmGate=new Promise(resolve=>releaseFm=resolve);
fmNow={...fmNow,track:{...fmNow.track,id:"another-fm-song"}};
await fmTick();const beforeFmSends=fmSent.length;
await fmTick();await fmTick();
assert.equal(fmSent.length,beforeFmSends+2,"slow FM detection cannot block lyric exchanges");
releaseFm();fmGate=null;await flush();
fmFailure=true;await fmTick();await fmTick();
assert.equal(fmSent.at(-1).fmActive,false,"failed detection does not enable a destructive action");
console.log("Native FM detection, dislike feedback, stale selection and nonblocking IPC checks passed");
