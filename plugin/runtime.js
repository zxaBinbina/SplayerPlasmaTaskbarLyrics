// SPDX-License-Identifier: AGPL-3.0-only
(function () {
  "use strict";
  let locale = String(splayer.locale || "zh-CN");
  splayer.register({
    events: ["trackChange", "lyricChange", "lineChange", "playStateChange"],
    controls: true,
    settings: []
  });
  const session = Date.now().toString(36) + "-" + Math.random().toString(36).slice(2);
  let track = null, lines = [], lyricRevision = 0, sentRevision = -1;
  let state = "idle", position = 0, duration = 0, speed = 1, offset = 0, volume = 1;
  let index = -1, busy = false, generation = 0, warned = false;
  let acknowledgements = [];
  const handled = new Set();
  const number = (value, fallback) => Number.isFinite(value) ? value : fallback;
  function setTrack(next) {
    const changed = !track !== !next || (track && next &&
      (track.id !== next.id || track.source !== next.source || track.path !== next.path));
    track = next;
    duration = next ? number(next.duration, 0) : 0;
    if (changed) {
      lines = []; index = -1; position = 0; generation++; lyricRevision++;
    }
  }
  splayer.player.on("trackChange", (data) => { setTrack(data.track); exchange(); });
  splayer.player.on("lyricChange", (data) => { lines = data.lines || []; lyricRevision++; exchange(); });
  splayer.player.on("lineChange", (data) => { index = data.index; position = data.position; });
  splayer.player.on("playStateChange", (data) => {
    state = data.state; position = data.position; generation++; exchange();
  });
  async function execute(command) {
    if (handled.has(command.id)) { acknowledgements.push(command.id); return; }
    // Remember before dispatch so a lost HTTP response cannot repeat a next/previous action.
    handled.add(command.id);
    if (handled.size > 256) handled.delete(handled.values().next().value);
    switch (command.action) {
      case "prev": splayer.player.prev(); break;
      case "next": splayer.player.next(); break;
      case "toggle": state === "playing" ? splayer.player.pause() : splayer.player.play(); break;
      case "seek":
        if (Number.isFinite(command.value)) splayer.player.seek(Math.max(0, command.value));
        break;
      case "volume":
        volume = Math.max(0, Math.min(1, volume + number(command.value, 0)));
        splayer.player.setVolume(volume); break;
    }
    acknowledgements.push(command.id);
  }
  async function exchange() {
    if (busy) return;
    busy = true;
    try {
      const observedGeneration = generation;
      const [now, status] = await Promise.all([
        splayer.player.getNowPlaying(), splayer.player.getStatus()
      ]);
      // Events received while queries were pending are newer than these snapshots.
      if (observedGeneration !== generation) return;
      setTrack(now.track);
      state = now.state;
      position = number(now.position, position);
      duration = number(status.durationMs, duration);
      speed = Math.max(0, number(now.speed, 1));
      offset = number(now.lyricOffsetMs, 0);
      volume = Math.max(0, Math.min(1, number(status.volume, volume)));
      const revision = lyricRevision;
      const ack = acknowledgements.slice();
      const payload = {
        protocol: 1, session, locale, lyricRevision: revision,
        playback: {
          state, position, duration, speed, offset, volume, index,
          // Query timestamp is authoritative; do not anchor at HTTP arrival time.
          timestamp: number(now.sendTimestamp, Date.now())
        },
        track
      };
      if (sentRevision !== revision) payload.lines = lines;
      const response = await splayer.request("http://127.0.0.1:43827/exchange", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-SPTL-Client": "plugin" },
        body: JSON.stringify({ ...payload, ack }),
        responseType: "json", timeout: 1500
      });
      if (response.status !== 200 || !response.body || response.body.protocol !== 1)
        throw new Error("SPTL bridge: HTTP " + response.status);
      if (response.body.locale && response.body.locale !== locale) {
        locale = response.body.locale;
      }
      warned = false;
      acknowledgements = acknowledgements.filter((id) => !ack.includes(id));
      sentRevision = response.body.needLines ? -1 : revision;
      for (const command of response.body.commands || []) await execute(command);
    } catch (error) {
      sentRevision = -1;
      if (!warned) {
        splayer.log.warn("SPTL: 辅助程序连接失败；将自动重连 / Bridge unavailable; retrying", String(error));
        warned = true;
      }
    } finally { busy = false; }
  }
  setInterval(exchange, 300);
  exchange();
})();
