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

# Avisos (flet-android-notifications): el proyecto Android que genera Flet
# necesita un PARCHE (receptores de alarmas en el manifest + "desugaring" en
# Gradle). Flet lo genera en el 1er build, así que puede tomar dos vueltas:
#   build -> (falla por desugaring) -> parche -> build otra vez
# y si Flet regeneró el proyecto sin el parche, se repite al final.
PARCHE="flet-android-notifications-patch"
MANIFEST="build/flutter/android/app/src/main/AndroidManifest.xml"
if ! command -v "$PARCHE" >/dev/null; then
  echo "✗ Falta $PARCHE. Instálalo con:  pip install -r requirements.txt"
  exit 1
fi
patch_android() {  # aplica el parche si ya existe el proyecto (no pasa nada si ya estaba)
  [[ -d build/flutter ]] && "$PARCHE" --project-root build/flutter | sed 's/^/  parche: /'
  return 0
}
patched() { grep -q "ScheduledNotificationReceiver" "$MANIFEST" 2>/dev/null; }

# Todo lo que imprime el build también queda en build_apk.log (para revisar errores).
# Extras: ./scripts/build_apk.sh -v   (más detalle)
LOG="build_apk.log"
echo "→ registro completo en $LOG"
build() {
  set +e
  flet build apk --build-version "$VERSION" --build-number "$BUILD" "$@" 2>&1 | tee "$LOG"
  ESTADO=${PIPESTATUS[0]}
  set -e
}

patch_android
build "$@"
if [[ $ESTADO -ne 0 ]] && grep -q -i "desugaring" "$LOG"; then
  echo; echo "→ Falta el parche de avisos (normal la 1a vez): aplicándolo y compilando otra vez…"
  patch_android
  build "$@"
fi
if [[ $ESTADO -eq 0 ]] && ! patched; then
  echo; echo "→ El APK salió sin los receptores de avisos: parche y otra vuelta…"
  patch_android
  build "$@"
fi
if [[ $ESTADO -eq 0 ]] && ! patched; then
  echo "✗ El APK no trae los receptores de avisos (los avisos no llegarían con la app cerrada)."
  exit 1
fi
if [[ $ESTADO -ne 0 ]]; then
  echo
  echo "✗ Falló el build. Las líneas con 'error' del registro:"
  grep -n -i -E "error|exception|failed" "$LOG" | grep -v -i "0 errors" | head -40
  exit "$ESTADO"
fi

echo
echo "✓ Listo:"
ls -lh build/apk/*.apk
