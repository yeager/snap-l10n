#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Daniel Nylander <daniel@danielnylander.se>

"""Snap Translation Status — main entry point."""

import sys
import locale
import gettext

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
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
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text(_("Refresh"))
        refresh_btn.connect("clicked", self._on_refresh)
        header.pack_end(refresh_btn)

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

        toolbar_view.set_content(self._stack)
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

    def _on_refresh(self, _btn):
        self._stack.set_visible_child_name("loading")
        self._status_page.set_title(_("Loading…"))
        self._status_page.set_icon_name("emblem-synchronizing-symbolic")
        self._status_page.set_description("")
        GLib.idle_add(self._load_snaps)


class SnapL10nApp(Adw.Application):
    """Main application class."""

    def __init__(self):
        super().__init__(
            application_id=APPID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = SnapL10nWindow(application=self)
        win.present()

    def _on_about(self, _action, _param):
        about = Adw.AboutWindow(
            transient_for=self.props.active_window,
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
            translator_credits=_("Translate this app: https://app.transifex.com/danielnylander/snap-l10n/"),
        )
        about.present()


def main():
    app = SnapL10nApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
