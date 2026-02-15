# snap-l10n

GTK4/Adwaita app showing translation status of installed snap packages.

## Features

- List installed snaps and their translation status
- Query snapd API for snap info
- Check .desktop files in snaps for translations
- Show which languages are present/missing per snap
- Color-coded status (complete/partial/none)
- Filter: all/untranslated/partial
- Link to snap store page

## License

GPL-3.0-or-later — Daniel Nylander <daniel@danielnylander.se>

## 🌍 Contributing Translations

Help translate this app into your language! All translations are managed via Transifex.

**→ [Translate on Transifex](https://app.transifex.com/danielnylander/snap-l10n/)**

### How to contribute:
1. Visit the [Transifex project page](https://app.transifex.com/danielnylander/snap-l10n/)
2. Create a free account (or log in)
3. Select your language and start translating

### Currently supported languages:
Arabic, Czech, Danish, German, Spanish, Finnish, French, Italian, Japanese, Korean, Norwegian Bokmål, Dutch, Polish, Brazilian Portuguese, Russian, Swedish, Ukrainian, Chinese (Simplified)

### Notes:
- Please do **not** submit pull requests with .po file changes — they are synced automatically from Transifex
- Source strings are pushed to Transifex daily via GitHub Actions
- Translations are pulled back and included in releases

New language? Open an [issue](https://github.com/yeager/snap-l10n/issues) and we'll add it!