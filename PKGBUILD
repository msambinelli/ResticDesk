# Maintainer: msambinelli

pkgname=resticdesk-git
pkgver=0
pkgrel=1
pkgdesc='ResticDesk: desktop GUI backup client based on Restic (development git package)'
arch=('x86_64' 'aarch64')
url='https://github.com/msambinelli/ResticDesk'
license=('GPL3')
depends=('python' 'python-pyqt6' 'python-psutil' 'python-peewee' 'python-packaging' 'restic')
makedepends=('git')
source=('git+https://github.com/msambinelli/ResticDesk.git')
sha256sums=('SKIP')

pkgver() {
  cd "$srcdir/ResticDesk"
  git describe --long --tags --abbrev=7 2>/dev/null | sed 's/^v//; s/-/.r/; s/-/./' || echo "0.r0"
}

package() {
  cd "$srcdir/ResticDesk"

  install -dm755 "$pkgdir/usr/lib/resticdesk"
  cp -r src "$pkgdir/usr/lib/resticdesk/"
  install -m644 pyproject.toml "$pkgdir/usr/lib/resticdesk/"
  install -m644 README.md "$pkgdir/usr/lib/resticdesk/"
  install -m644 LICENSE.txt "$pkgdir/usr/lib/resticdesk/"

  install -dm755 "$pkgdir/usr/bin"
  cat > "$pkgdir/usr/bin/resticdesk" <<'LAUNCHER'
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/resticdesk/src:${PYTHONPATH}"
exec python3 -m vorta "$@"
LAUNCHER
  chmod 755 "$pkgdir/usr/bin/resticdesk"

  install -dm755 "$pkgdir/usr/share/applications"
  sed \
    -e 's/^Name=.*/Name=ResticDesk/' \
    -e 's/^Exec=.*/Exec=resticdesk/' \
    -e 's/^Icon=.*/Icon=resticdesk/' \
    src/vorta/assets/metadata/com.borgbase.Vorta.desktop \
    > "$pkgdir/usr/share/applications/resticdesk.desktop"

  install -dm755 "$pkgdir/usr/share/icons/hicolor/scalable/apps"
  install -m644 src/vorta/assets/icons/icon.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/resticdesk.svg"
}
