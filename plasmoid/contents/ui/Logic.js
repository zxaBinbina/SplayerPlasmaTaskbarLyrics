.pragma library
// SPDX-License-Identifier: AGPL-3.0-only
function currentIndex(lines, position) {
    var selected = -1, latest = -1;
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (line.isBG || !line.timed || line.startTime > position) continue;
        if (line.startTime >= latest) { selected = i; latest = line.startTime; }
    }
    return selected;
}
function auxiliary(line, mode) {
    if (!line) return "";
    return mode === "translation" ? line.translatedLyric :
           mode === "romanization" ? line.romanLyric : "";
}
function auxiliaryWords(line, mode) {
    if (!line || mode !== "romanization" || !line.wordTimed ||
        !line.words.every(function(w) { return !!w.romanWord; }) ||
        line.words.map(function(w) { return w.romanWord; }).join("") !== line.romanLyric) return [];
    return line.words.map(function(w) {
        return { word: w.romanWord, startTime: w.startTime, endTime: w.endTime };
    });
}
function nextLine(lines, index) {
    for (var i = index + 1; i < lines.length; i++)
        if (!lines[i].isBG && lines[i].text) return lines[i].text;
    return "";
}
function display(lines, index, track, settings, hovered, idle, unknown) {
    if (!track) return { primary: idle, secondary: "SPlayer Next", words: [] };
    if (hovered) return { primary: track.title, secondary: track.artists || unknown, words: [] };
    var line = index >= 0 ? lines[index] : null;
    if (!line) return { primary: track.title, secondary: track.artists || unknown, words: [] };
    var aux = auxiliary(line, settings.auxiliary);
    var prefer = settings.lyricMode === "single" && settings.singlePreferAux && !!aux;
    var words = line.wordTimed ? line.words : [];
    if (prefer) words = auxiliaryWords(line, settings.auxiliary);
    return {
        primary: prefer ? aux : line.text,
        secondary: settings.lyricMode === "single" ?
            track.title + " · " + (track.artists || unknown) : aux || nextLine(lines, index),
        words: words,
        secondaryWords: settings.lyricMode === "double" && aux ? auxiliaryWords(line, settings.auxiliary) : []
    };
}
function wordProgress(word, position) {
    if (position < word.startTime) return 0;
    if (word.endTime <= word.startTime || position >= word.endTime) return 1;
    return Math.max(0, Math.min(1, (position - word.startTime) / (word.endTime - word.startTime)));
}
function formatTime(position) {
    var seconds = Math.floor(Math.max(0, position) / 1000);
    return Math.floor(seconds / 60) + ":" + ("0" + (seconds % 60)).slice(-2);
}
function width(mode, fixed, maximum, text, cover, controls, gap) {
    var total = cover + controls + gap + Math.max(40, text + 8);
    return Math.round(mode === "fixed" ? fixed : Math.min(maximum, total));
}
