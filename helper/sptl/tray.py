# SPDX-License-Identifier: AGPL-3.0-only
"""Use SP's standard Linux tray menu for its source-aware favorite operation."""
import ast
import re
import subprocess
import time


FAVORITE_LABELS = {"添加到我喜欢": False, "从我喜欢中移除": True,
                   "Add to Liked": False, "Remove from Liked": True}


def favorite_item(layout):
    # Request only label/enabled, never the menu's potentially large icon data.
    # Each direct child in a depth-one GetLayout response has an empty child list.
    for item in re.finditer(r"<\((\d+), \{(.*?)\}, @av \[\]\)>", layout, re.DOTALL):
        label = re.search(r"'label': <('(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")>", item[2])
        if not label:
            continue
        try:
            text = ast.literal_eval(label[1])
        except (ValueError, SyntaxError):
            continue
        if text in FAVORITE_LABELS:
            return {"id": int(item[1]), "liked": FAVORITE_LABELS[text],
                    "available": not bool(re.search(r"'enabled': <false>", item[2]))}
    return None


class TrayFavorite:
    @staticmethod
    def call(destination, path, method, *args):
        result = subprocess.run(
            ["gdbus", "call", "--session", "--dest", destination,
             "--object-path", path, "--method", method, *args],
            capture_output=True, text=True, timeout=2, check=False)
        if result.returncode:
            raise ValueError("SP tray is unavailable")
        return result.stdout

    def inspect(self, names=None):
        try:
            if names is None:
                names = self.call("org.freedesktop.DBus", "/org/freedesktop/DBus",
                                  "org.freedesktop.DBus.ListNames")
            for destination in re.findall(r"'(org\.freedesktop\.StatusNotifierItem-\d+-\d+)'", names):
                identifier = self.call(destination, "/StatusNotifierItem",
                    "org.freedesktop.DBus.Properties.Get", "org.kde.StatusNotifierItem", "Id")
                if not re.search(r"<'SPlayer[-_]Next_status_icon_", identifier):
                    continue
                menu = self.call(destination, "/StatusNotifierItem",
                    "org.freedesktop.DBus.Properties.Get", "org.kde.StatusNotifierItem", "Menu")
                path = re.search(r"objectpath '([/A-Za-z0-9_]+)'", menu)
                if not path:
                    continue
                layout = self.call(destination, path[1], "com.canonical.dbusmenu.GetLayout",
                                   "0", "1", "['label', 'enabled']")
                item = favorite_item(layout)
                if item:
                    return dict(item, destination=destination, path=path[1])
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        return {"available": False, "liked": False}

    def toggle(self):
        # Electron replaces the menu IDs on every state change. Resolve afresh.
        item = self.inspect()
        if not item["available"]:
            raise ValueError("SP favorite menu is unavailable")
        self.call(item["destination"], item["path"], "com.canonical.dbusmenu.Event",
                  str(item["id"]), "clicked", "<int32 0>", str(int(time.time() * 1000) % 2**32))
