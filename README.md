# Snap Translation Status

## Screenshot

![Ubuntu L10n](screenshots/main.png)

A GTK4/Adwaita application for viewing translation status of installed Snap packages.

![Screenshot](data/screenshots/screenshot-01.png)

## Features

- List installed snaps and their translation status
- Query snapd API for snap info
- Check .desktop files in snaps for translations
- Show which languages are present/missing per snap
- Color-coded status (complete/partial/none)
- Filter: all/untranslated/partial
- Link to snap store page

## Installation

### Debian/Ubuntu

```bash
# Add repository
curl -fsSL https://yeager.github.io/debian-repo/KEY.gpg | sudo gpg --dearmor -o /usr/share/keyrings/yeager-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/yeager-archive-keyring.gpg] https://yeager.github.io/debian-repo stable main" | sudo tee /etc/apt/sources.list.d/yeager.list
sudo apt update
sudo apt install snap-l10n
```

### Fedora/RHEL

```bash
sudo dnf config-manager --add-repo https://yeager.github.io/rpm-repo/yeager.repo
sudo dnf install snap-l10n
```

### From source

```bash
pip install .
snap-l10n
```

## 🌍 Contributing Translations

This app is translated via Transifex. Help translate it into your language!

**[→ Translate on Transifex](https://app.transifex.com/danielnylander/snap-l10n/)**

Currently supported: Swedish (sv). More languages welcome!

### For Translators
1. Create a free account at [Transifex](https://www.transifex.com)
2. Join the [danielnylander](https://app.transifex.com/danielnylander/) organization
3. Start translating!

Translations are automatically synced via GitHub Actions.
## License

GPL-3.0-or-later — Daniel Nylander <daniel@danielnylander.se>
