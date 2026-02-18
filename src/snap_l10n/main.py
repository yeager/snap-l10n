#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Daniel Nylander <daniel@danielnylander.se>

"""Snap Translation Status — main entry point."""

import csv
import sys
import locale
import gettext
import json

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
# Optional desktop notifications
try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify as _Notify
    HAS_NOTIFY = True
except (ValueError, ImportError):
    HAS_NOTIFY = False
from gi.repository import Gtk, Adw, Gio, GLib, Pango, Gdk  # noqa: E402

from snap_l10n.snapd import get_installed_snaps, get_snap_l10n_info  # noqa: E402

APPID = "se.danielnylander.SnapL10n"
GETTEXT_DOMAIN = "snap-l10n"

locale.bindtextdomain(GETTEXT_DOMAIN, "/usr/share/locale")
locale.textdomain(GETTEXT_DOMAIN)
gettext.bindtextdomain(GETTEXT_DOMAIN, "/usr/share/locale")
gettext.textdomain(GETTEXT_DOMAIN)
_ = gettext.gettext


def _setup_heatmap_css():
    css = b"""
    .heatmap-green { background-color: #26a269; color: white; border-radius: 8px; }
    .heatmap-yellow { background-color: #e5a50a; color: white; border-radius: 8px; }
    .heatmap-red { background-color: #c01c28; color: white; border-radius: 8px; }
    .heatmap-gray { background-color: #77767b; color: white; border-radius: 8px; }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


_SNAP_STATUS_CSS = {"full": "heatmap-green", "partial": "heatmap-yellow", "none": "heatmap-red"}
_SNAP_STATUS_PCT = {"full": "100%", "partial": "~50%", "none": "0%"}



import json as _json
import platform as _platform
from pathlib import Path as _Path

_NOTIFY_APP = "snap-l10n"


def _notify_config_path():
    return _Path(GLib.get_user_config_dir()) / _NOTIFY_APP / "notifications.json"


def _load_notify_config():
    try:
        return _json.loads(_notify_config_path().read_text())
    except Exception:
        return {"enabled": False}


def _save_notify_config(config):
    p = _notify_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_json.dumps(config))


def _send_notification(summary, body="", icon="dialog-information"):
    if HAS_NOTIFY and _load_notify_config().get("enabled"):
        try:
            n = _Notify.Notification.new(summary, body, icon)
            n.show()
        except Exception:
            pass


def _get_system_info():
    return "\n".join([
        f"App: Snap Translation Status",
        f"Version: {"0.1.0"}",
        f"GTK: {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
        f"Adw: {Adw.get_major_version()}.{Adw.get_minor_version()}.{Adw.get_micro_version()}",
        f"Python: {_platform.python_version()}",
        f"OS: {_platform.system()} {_platform.release()} ({_platform.machine()})",
    ])


class SnapRow(Gtk.ListBoxRow):
    """A row representing one snap and its l10n status."""

    def __init__(self, info: dict):
        super().__init__()
        self.info = info
        self.set_margin_top(4)
        self.set_margin_bottom(4)
        self.set_margin_start(8)
        self.set_margin_end(8)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        self.set_child(box)

        # Status indicator
        status = info["status"]
        color_map = {"full": "success", "partial": "warning", "none": "error"}
        css_class = color_map.get(status, "error")

        indicator = Gtk.Label(label="●")
        indicator.add_css_class(css_class)
        indicator.set_valign(Gtk.Align.CENTER)
        box.append(indicator)

        # Info column
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vbox.set_hexpand(True)

        name_label = Gtk.Label(label=info["name"], xalign=0)
        name_label.add_css_class("heading")
        vbox.append(name_label)

        detail = _("Version: {version} · Publisher: {publisher}").format(
            version=info.get("version", "?"),
            publisher=info.get("publisher", _("unknown")),
        )
        detail_label = Gtk.Label(label=detail, xalign=0)
        detail_label.add_css_class("dim-label")
        detail_label.set_ellipsize(Pango.EllipsizeMode.END)
        vbox.append(detail_label)

        langs = info.get("languages", [])
        if langs:
            lang_text = _("Languages: {langs}").format(langs=", ".join(sorted(langs)))
        else:
            lang_text = _("No translations found")
        lang_label = Gtk.Label(label=lang_text, xalign=0)
        lang_label.set_ellipsize(Pango.EllipsizeMode.END)
        lang_label.set_wrap(True)
        lang_label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lang_label.add_css_class("caption")
        vbox.append(lang_label)

        desktop_info = info.get("desktop_l10n")
        if desktop_info is not None:
            if desktop_info:
                dt_text = _("Desktop file translated: {langs}").format(
                    langs=", ".join(sorted(desktop_info))
                )
            else:
                dt_text = _("Desktop file: not translated")
            dt_label = Gtk.Label(label=dt_text, xalign=0)
            dt_label.add_css_class("caption")
            dt_label.set_ellipsize(Pango.EllipsizeMode.END)
            vbox.append(dt_label)

        status_text_map = {
            "full": _("Fully translated"),
            "partial": _("Partially translated"),
            "none": _("No translations"),
        }
        status_label = Gtk.Label(label=status_text_map.get(status, status), xalign=0)
        status_label.add_css_class(css_class)
        status_label.add_css_class("caption")
        vbox.append(status_label)

        box.append(vbox)

        # Store link button
        link_btn = Gtk.Button(icon_name="web-browser-symbolic")
        link_btn.set_valign(Gtk.Align.CENTER)
        link_btn.set_tooltip_text(_("Open in Snap Store"))
        link_btn.connect("clicked", self._on_store_clicked)
        box.append(link_btn)

    def _on_store_clicked(self, _btn):
        url = f"https://snapcraft.io/{self.info['name']}"
        Gio.AppInfo.launch_default_for_uri(url, None)


class SnapL10nWindow(Adw.ApplicationWindow):
    """Main application window."""

    FILTER_ALL = 0
    FILTER_NONE = 1
    FILTER_PARTIAL = 2

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(_("Snap Translation Status"))
        self.set_default_size(700, 600)

        self._snaps = []
        self._current_filter = self.FILTER_ALL
        self._current_language = None  # None = all languages
        self._heatmap_mode = False

        _setup_heatmap_css()

        # Detect system language
        try:
            sys_locale = locale.getlocale()[0] or ""
            self._system_lang = sys_locale.split("_")[0] if sys_locale else ""
        except Exception:
            self._system_lang = ""

        # Header bar
        header = Adw.HeaderBar()

        # Filter dropdown
        filter_model = Gtk.StringList.new([
            _("All snaps"),
            _("No translations"),
            _("Partially translated"),
        ])
        self._filter_dropdown = Gtk.DropDown(model=filter_model)
        self._filter_dropdown.connect("notify::selected", self._on_filter_changed)
        header.pack_start(self._filter_dropdown)

        # Language picker dropdown
        self._lang_model = Gtk.StringList.new([_("All languages")])
        self._lang_dropdown = Gtk.DropDown(model=self._lang_model)
        self._lang_dropdown.set_tooltip_text(_("Filter by language"))
        self._lang_dropdown.connect("notify::selected", self._on_language_changed)
        header.pack_start(self._lang_dropdown)

        # Heatmap toggle
        self._heatmap_btn = Gtk.ToggleButton(icon_name="view-grid-symbolic")
        self._heatmap_btn.set_tooltip_text(_("Toggle heatmap view"))
        self._heatmap_btn.connect("toggled", self._on_heatmap_toggled)
        header.pack_start(self._heatmap_btn)

        # Refresh button
        # Notifications toggle
        notif_btn = Gtk.ToggleButton(icon_name="preferences-system-notifications-symbolic")
        notif_btn.set_tooltip_text(_("Toggle notifications"))
        notif_btn.set_active(_load_notify_config().get("enabled", False))
        notif_btn.connect("toggled", self._on_notif_toggled)
        header.pack_end(notif_btn)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh"))
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_end(refresh_btn)

        # Export button
        export_btn = Gtk.Button(icon_name="document-save-symbolic",
                                tooltip_text=_("Export data"))
        export_btn.connect("clicked", self._on_export_clicked)
        header.pack_end(export_btn)

        # Theme toggle
        self._theme_btn = Gtk.Button(icon_name="weather-clear-night-symbolic",
                                     tooltip_text="Toggle dark/light theme")
        self._theme_btn.connect("clicked", self._on_theme_toggle)
        header.pack_end(self._theme_btn)

        # Layout
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)

        self._status_page = Adw.StatusPage(
            title=_("Loading…"),
            icon_name="emblem-synchronizing-symbolic",
        )

        self._scrolled = Gtk.ScrolledWindow(vexpand=True)
        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._listbox.add_css_class("boxed-list")
        self._listbox.set_margin_top(12)
        self._listbox.set_margin_bottom(12)
        self._listbox.set_margin_start(12)
        self._listbox.set_margin_end(12)
        self._scrolled.set_child(self._listbox)

        # Heatmap view
        heatmap_scroll = Gtk.ScrolledWindow(vexpand=True)
        self._heatmap_flow = Gtk.FlowBox()
        self._heatmap_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._heatmap_flow.set_homogeneous(True)
        self._heatmap_flow.set_min_children_per_line(3)
        self._heatmap_flow.set_max_children_per_line(8)
        self._heatmap_flow.set_column_spacing(4)
        self._heatmap_flow.set_row_spacing(4)
        self._heatmap_flow.set_margin_start(12)
        self._heatmap_flow.set_margin_end(12)
        self._heatmap_flow.set_margin_top(12)
        self._heatmap_flow.set_margin_bottom(12)
        heatmap_scroll.set_child(self._heatmap_flow)

        self._stack = Gtk.Stack()
        self._stack.add_named(self._status_page, "loading")
        self._stack.add_named(self._scrolled, "list")
        self._stack.add_named(heatmap_scroll, "heatmap")
        self._stack.set_visible_child_name("loading")

        # Status bar
        self._status_bar = Gtk.Label(label="", halign=Gtk.Align.START,
                                     margin_start=12, margin_end=12, margin_bottom=4)
        self._status_bar.add_css_class("dim-label")
        self._status_bar.add_css_class("caption")
        _content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        _content_box.append(self._stack)
        _content_box.append(self._status_bar)
        toolbar_view.set_content(_content_box)
        self.set_content(toolbar_view)

        # Load data async
        GLib.idle_add(self._load_snaps)

    def _load_snaps(self):
        try:
            snaps = get_installed_snaps()
            self._snaps = [get_snap_l10n_info(s) for s in snaps]
            self._snaps.sort(key=lambda s: s["name"])
        except Exception as e:
            self._status_page.set_title(_("Error"))
            self._status_page.set_description(str(e))
            self._status_page.set_icon_name("dialog-error-symbolic")
            return False
        self._update_language_list()
        self._populate()
        # Notify about untranslated snaps
        no_l10n = [s["name"] for s in self._snaps if s["status"] == "none"]
        if no_l10n:
            _send_notification(
                _("Snap L10n: Untranslated snaps"),
                _("{count} snaps have no translations").format(count=len(no_l10n)),
                "snap-l10n")
        return False

    def _update_language_list(self):
        """Collect all languages from snaps and populate the language dropdown."""
        all_langs = set()
        for info in self._snaps:
            all_langs.update(info.get("languages", []))
            dl = info.get("desktop_l10n")
            if dl:
                all_langs.update(dl)

        self._all_languages = sorted(all_langs)

        # Rebuild model
        self._lang_model.splice(0, self._lang_model.get_n_items(), [])
        self._lang_model.append(_("All languages"))
        for lang in self._all_languages:
            self._lang_model.append(lang)

        # Auto-select system language if available
        if self._system_lang and self._system_lang in self._all_languages:
            idx = self._all_languages.index(self._system_lang) + 1  # +1 for "All"
            self._lang_dropdown.set_selected(idx)
        else:
            self._lang_dropdown.set_selected(0)

    def _populate(self):
        # Clear
        while True:
            row = self._listbox.get_row_at_index(0)
            if row is None:
                break
            self._listbox.remove(row)

        count = 0
        for info in self._snaps:
            if self._current_filter == self.FILTER_NONE and info["status"] != "none":
                continue
            if self._current_filter == self.FILTER_PARTIAL and info["status"] != "partial":
                continue
            # Language filter
            if self._current_language is not None:
                snap_langs = set(info.get("languages", []))
                dl = info.get("desktop_l10n")
                if dl:
                    snap_langs.update(dl)
                if self._current_language not in snap_langs:
                    continue
            self._listbox.append(SnapRow(info))
            count += 1

        # Rebuild heatmap
        while True:
            child = self._heatmap_flow.get_first_child()
            if child is None:
                break
            self._heatmap_flow.remove(child)
        heatmap_count = 0
        for info in self._snaps:
            if self._current_filter == self.FILTER_NONE and info["status"] != "none":
                continue
            if self._current_filter == self.FILTER_PARTIAL and info["status"] != "partial":
                continue
            if self._current_language is not None:
                snap_langs = set(info.get("languages", []))
                dl = info.get("desktop_l10n")
                if dl:
                    snap_langs.update(dl)
                if self._current_language not in snap_langs:
                    continue
            status = info["status"]
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_size_request(140, 64)
            box.add_css_class(_SNAP_STATUS_CSS.get(status, "heatmap-gray"))
            box.set_margin_start(4)
            box.set_margin_end(4)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            lbl = Gtk.Label(label=info["name"])
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.set_max_width_chars(18)
            lbl.set_margin_top(6)
            lbl.set_margin_start(6)
            lbl.set_margin_end(6)
            box.append(lbl)
            st_lbl = Gtk.Label(label=_SNAP_STATUS_PCT.get(status, "?"))
            st_lbl.set_margin_bottom(6)
            box.append(st_lbl)
            n_langs = len(info.get("languages", []))
            box.set_tooltip_text(f"{info['name']}: {n_langs} languages")
            gesture = Gtk.GestureClick()
            gesture.connect("released", lambda g, n, x, y, name=info["name"]: Gio.AppInfo.launch_default_for_uri(f"https://snapcraft.io/{name}", None))
            box.add_controller(gesture)
            box.set_cursor(Gdk.Cursor.new_from_name("pointer"))
            self._heatmap_flow.append(box)
            heatmap_count += 1

        if count == 0 and heatmap_count == 0:
            self._status_page.set_title(_("No snaps found"))
            self._status_page.set_description(
                _("No snaps match the current filter.")
            )
            self._status_page.set_icon_name("edit-find-symbolic")
            self._stack.set_visible_child_name("loading")
        elif self._heatmap_mode:
            self._stack.set_visible_child_name("heatmap")
        else:
            self._stack.set_visible_child_name("list")

        self._update_status_bar()

    def _on_heatmap_toggled(self, btn):
        self._heatmap_mode = btn.get_active()
        if self._snaps:
            self._populate()

    def _on_filter_changed(self, dropdown, _param):
        self._current_filter = dropdown.get_selected()
        self._populate()

    def _on_language_changed(self, dropdown, _param):
        idx = dropdown.get_selected()
        if idx == 0:
            self._current_language = None
        else:
            self._current_language = self._all_languages[idx - 1]
        self._populate()

    def _on_notif_toggled(self, btn):
        config = _load_notify_config()
        config["enabled"] = btn.get_active()
        _save_notify_config(config)

    def _on_export_clicked(self, *_args):
        dialog = Adw.MessageDialog(transient_for=self,
                                   heading=_("Export Data"),
                                   body=_("Choose export format:"))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("csv", "CSV")
        dialog.add_response("json", "JSON")
        dialog.set_response_appearance("csv", Adw.ResponseAppearance.SUGGESTED)
        dialog.connect("response", self._on_export_format_chosen)
        dialog.present()

    def _on_export_format_chosen(self, dialog, response):
        if response not in ("csv", "json"):
            return
        self._export_fmt = response
        fd = Gtk.FileDialog()
        fd.set_initial_name(f"snap-l10n.{response}")
        fd.save(self, None, self._on_export_save)

    def _on_export_save(self, dialog, result):
        try:
            path = dialog.save_finish(result).get_path()
        except Exception:
            return
        data = [{"name": s.get("name", ""), "status": s.get("status", ""),
                 "languages": len(s.get("languages", [])),
                 "desktop_l10n": s.get("desktop_l10n", False)}
                for s in self._snaps]
        if not data:
            return
        if self._export_fmt == "csv":
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=data[0].keys())
                w.writeheader()
                w.writerows(data)
        else:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def _on_refresh(self, _btn):
        self._stack.set_visible_child_name("loading")
        self._status_page.set_title(_("Loading…"))
        self._status_page.set_icon_name("emblem-synchronizing-symbolic")
        self._status_page.set_description("")
        GLib.idle_add(self._load_snaps)



    def _on_theme_toggle(self, _btn):
        sm = Adw.StyleManager.get_default()
        if sm.get_color_scheme() == Adw.ColorScheme.FORCE_DARK:
            sm.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            self._theme_btn.set_icon_name("weather-clear-night-symbolic")
        else:
            sm.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            self._theme_btn.set_icon_name("weather-clear-symbolic")

    def _update_status_bar(self):
        from datetime import datetime
        total = len(self._snaps)
        translated = sum(1 for s in self._snaps if s["status"] != "none")
        filter_names = {
            self.FILTER_ALL: _("All snaps"),
            self.FILTER_NONE: _("No translations"),
            self.FILTER_PARTIAL: _("Partially translated"),
        }
        filter_text = filter_names.get(self._current_filter, "")
        lang_text = self._current_language or _("All languages")
        ts = datetime.now().strftime("%H:%M:%S")
        self._status_bar.set_text(
            _("{total} snaps · {translated} translated · {filter} · {lang} · {ts}").format(
                total=total, translated=translated, filter=filter_text, lang=lang_text, ts=ts)
        )


class SnapL10nApp(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(
            application_id=APPID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        if HAS_NOTIFY:
            _Notify.init(_NOTIFY_APP)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.refresh", ["F5"])
        self.set_accels_for_action("app.shortcuts", ["<Control>slash"])
        self.set_accels_for_action("app.export", ["<Control>e"])
        for n, cb in [("quit", lambda *_: self.quit()),
                      ("refresh", lambda *_: self._do_refresh()),
                      ("shortcuts", self._show_shortcuts_window),
                      ("export", lambda *_: self.get_active_window() and self.get_active_window()._on_export_clicked())]:
            a = Gio.SimpleAction.new(n, None); a.connect("activate", cb); self.add_action(a)

    def _do_refresh(self):
        w = self.get_active_window()
        if w: w._on_refresh(None)

    def _show_shortcuts_window(self, *_args):
        win = Gtk.ShortcutsWindow(transient_for=self.get_active_window(), modal=True)
        section = Gtk.ShortcutsSection(visible=True, max_height=10)
        group = Gtk.ShortcutsGroup(visible=True, title="General")
        for accel, title in [("<Control>q", "Quit"), ("F5", "Refresh"), ("<Control>slash", "Keyboard shortcuts")]:
            s = Gtk.ShortcutsShortcut(visible=True, accelerator=accel, title=title)
            group.append(s)
        section.append(group)
        win.add_child(section)
        win.present()

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = SnapL10nWindow(application=self)
        win.present()

    def _on_about(self, _action, _param):
        about = Adw.AboutDialog(
            application_name=_("Snap Translation Status"),
            application_icon="snap-l10n",
            developer_name="Daniel Nylander",
            version="0.1.0",
            developers=["Daniel Nylander <daniel@danielnylander.se>"],
            copyright="© 2026 Daniel Nylander",
            license_type=Gtk.License.GPL_3_0,
            website="https://github.com/yeager/snap-l10n",
            issue_url="https://github.com/yeager/snap-l10n/issues",
            translate_url="https://app.transifex.com/danielnylander/snap-l10n/",
            comments=_("A localization tool by Daniel Nylander"),
            translator_credits=_("Translate this app: https://www.transifex.com/danielnylander/snap-l10n/"),
        )
        about.set_debug_info(_get_system_info())
        about.set_debug_info_filename("snap-l10n-debug.txt")
        about.present(self.props.active_window)


def main():
    app = SnapL10nApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
