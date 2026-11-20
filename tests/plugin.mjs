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
const splayer = {
  locale:"en-US",
  getSetting: () => undefined,
  onSettingChange: (key, callback) => updates[key] = callback,
  register: (data) => registered = {...registered, ...data},
  log: {warn: () => {}},
  player: {
    on: (event, handler) => events[event] = handler,
    getNowPlaying: async () => now,
    getStatus: async () => ({durationMs:10000, volume:0.5}),
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
