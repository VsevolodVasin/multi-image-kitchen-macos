# Multi Image Kitchen for macOS

Распаковка и сборка Amlogic-образов и ext4-разделов (Khadas VIM3 / VIM3L).

Прошивка по USB: [usb-burning-tool-macos](https://github.com/VsevolodVasin/usb-burning-tool-macos).

## Install

```bash
git clone https://github.com/VsevolodVasin/multi-image-kitchen-macos.git
cd multi-image-kitchen-macos
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
brew install e2fsprogs
./MIK.command
```

Либо: `.venv/bin/python -m mik`

## DMG

```bash
./scripts/build_dmg.sh
```

Готовые сборки: [Releases](https://github.com/VsevolodVasin/multi-image-kitchen-macos/releases).

## License

GPL-3.0. Сторонние компоненты: [THIRD_PARTY.md](THIRD_PARTY.md).

Основано на [ColdWindScholar/MIK](https://github.com/ColdWindScholar/MIK) (AGPL) и утилитах [Khadas](https://github.com/khadas/utils).
