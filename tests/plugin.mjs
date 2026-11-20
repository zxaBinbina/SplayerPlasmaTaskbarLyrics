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
releaseQueue(); queueGate = null; await flush();
timers[0](); await flush();
assert.equal(sent.at(-1).queue.requestId, 12);
assert.ok(sent.at(-1).ack.includes(12));
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
