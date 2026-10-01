#!/usr/bin/env bash
# Genera el APK de producción de ControlKraken, firmado con TU llave.
#
#   ./scripts/build_apk.sh
#
# Primera vez: crea la llave (una sola vez en la vida de la app; ver docs/apk.md).
# Resultado: build/apk/*.apk
set -euo pipefail
cd "$(dirname "$0")/.."

LLAVE="${CK_KEYSTORE:-$HOME/.claves/controlkraken-upload.jks}"
if [[ ! -f "$LLAVE" ]]; then
  echo "✗ No encuentro la llave de firma: $LLAVE"
  echo "  Créala una vez con:"
  echo "    mkdir -p ~/.claves && keytool -genkey -v -keystore $LLAVE \\"
  echo "      -keyalg RSA -keysize 2048 -validity 10000 -alias upload"
  exit 1
fi

read -rsp "Contraseña de la llave: " CLAVE; echo
export FLET_ANDROID_SIGNING_KEY_STORE="$LLAVE"
export FLET_ANDROID_SIGNING_KEY_STORE_PASSWORD="$CLAVE"
export FLET_ANDROID_SIGNING_KEY_PASSWORD="$CLAVE"
export FLET_ANDROID_SIGNING_KEY_ALIAS="upload"

# Versión que ve el usuario (0.14.2) y número interno que SIEMPRE sube (commits)
VERSION=$(python -c "from core import APP_VERSION; print(APP_VERSION)")
BUILD=$(git rev-list --count HEAD)
echo "→ ControlKraken $VERSION (build $BUILD)"

flet build apk --build-version "$VERSION" --build-number "$BUILD"

echo
echo "✓ Listo:"
ls -lh build/apk/*.apk
