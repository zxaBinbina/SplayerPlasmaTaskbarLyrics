# SPDX-License-Identifier: AGPL-3.0-only
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "helper"))
from sptl.tray import TrayFavorite, favorite_item


def layout(identifier=290, label="从我喜欢中移除", enabled=True):
    disabled = ", 'enabled': <false>" if not enabled else ""
    return f"(uint32 16, (0, @a{{sv}} {{}}, [<({identifier}, {{'label': <'{label}'>{disabled}}}, @av [])>]))"


class TrayTests(unittest.TestCase):
    def test_labels_and_disabled_state(self):
        for label, liked in (("从我喜欢中移除", True), ("添加到我喜欢", False),
                             ("Remove from Liked", True), ("Add to Liked", False)):
            item = favorite_item(layout(label=label))
            self.assertEqual(item, {"id": 290, "liked": liked, "available": True})
        self.assertFalse(favorite_item(layout(enabled=False))["available"])
        self.assertIsNone(favorite_item(layout(label="退出")))

    def test_recreated_menu_ids_are_resolved_before_clicking(self):
        calls = []
        def call(destination, path, method, *args):
            calls.append((destination, path, method, args))
            if method.endswith("ListNames"):
                return "(['org.freedesktop.StatusNotifierItem-123-1'],)"
            if args and args[-1] == "Id": return "(<'SPlayer-Next_status_icon_1'>,)"
            if args and args[-1] == "Menu": return "(<objectpath '/com/canonical/dbusmenu'>,)"
            if method.endswith("GetLayout"): return layout(identifier=999)
            return "()"
        with patch.object(TrayFavorite, "call", side_effect=call):
            tray = TrayFavorite()
            tray.toggle()
        self.assertEqual(calls[-1][2], "com.canonical.dbusmenu.Event")
        self.assertEqual(calls[-1][3][:3], ("999", "clicked", "<int32 0>"))

    def test_disabled_or_missing_tray_never_dispatches_a_click(self):
        with patch.object(TrayFavorite, "inspect", return_value={"available": False, "liked": False}), \
             patch.object(TrayFavorite, "call") as call:
            with self.assertRaises(ValueError): TrayFavorite().toggle()
            call.assert_not_called()


if __name__ == "__main__":
    unittest.main()
