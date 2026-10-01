# APK de ControlKraken (Android)

```
 tu compu                                         tu celular
 ./scripts/build_apk.sh  ──►  build/apk/*.apk  ──►  instalar  ──►  ControlKraken
   (flet build apk, firmado con TU llave)            (datos en la carpeta privada de la app)
```

## 0. Una sola vez: crear tu llave de firma

Android solo instala una **actualización** si viene firmada con la **misma llave**
que la versión instalada. Si la pierdes, para actualizar tendrás que
desinstalar… y desinstalar **borra los datos de la app**. Guárdala como oro
(respáldala fuera de la compu: USB, gestor de contraseñas, Drive privado).

```bash
mkdir -p ~/.claves
keytool -genkey -v -keystore ~/.claves/controlkraken-upload.jks \
  -keyalg RSA -keysize 2048 -validity 10000 -alias upload
```

- Te pide una contraseña (anótala) y datos (nombre, ciudad…; puedes dar Enter).
- `keytool` viene con Java. Si no lo tienes: `sudo apt install openjdk-17-jdk-headless`.
- La llave vive en `~/.claves/`, FUERA del repo (y `*.jks` está en `.gitignore`).

## 1. Generar el APK

```bash
cd ~/workspace_personal/pruebas_flet
source .venv/bin/activate
pip install -r requirements.txt     # flet[all] trae el comando `flet build`
./scripts/build_apk.sh              # o: bash scripts/build_apk.sh
```

- **La primera vez tarda** (10–30 min): `flet build` descarga solo Flutter,
  el SDK de Android y Java si faltan (varios GB). Las siguientes, unos minutos.
- Pide la contraseña de la llave (no se guarda en ningún archivo).
- Versión que ves en el celular = `APP_VERSION` de `core/__init__.py`.
  Número interno (`--build-number`) = número de commits: siempre sube, que es
  lo que Android exige para aceptar una actualización. **Haz commit antes de
  generar cada APK nuevo.**
- Resultado: `build/apk/ControlKraken.apk` (o parecido; el script lo lista).

## 2. Instalarlo en el celular

- Pasa el `.apk` al celular (cable, Drive, Telegram…) y ábrelo.
- Android pedirá permitir "instalar apps de origen desconocido" para la app con
  la que lo abriste (Archivos, Drive…). Es normal fuera de la Play Store.
- Por cable con el celular en modo desarrollador: `adb install -r build/apk/*.apk`
  (`-r` = actualizar conservando datos).

## 3. Actualizar

Mismo proceso: commit → `./scripts/build_apk.sh` → instalar encima.
Los datos se conservan (misma llave + build number mayor). Si la versión trae
migraciones nuevas, la app hace una copia en `respaldos/` y migra al abrir,
igual que en la compu.

## Qué es distinto en el celular (instalada)

| | Compu (`flet run`) | Celular (APK) |
|---|---|---|
| BD y `data/` | junto a `main.py` | carpeta privada de la app (`FLET_APP_STORAGE_DATA`) |
| Respaldos `.zip` | `~/Respaldos/ControlKraken` | dentro de la carpeta privada |
| Subir a Drive | rclone ✓ | ✗ (rclone no existe en Android) — pendiente: login con Google |
| Captura / grabación | ✓ | ✓ |

**Pasar tus datos de la compu al celular:** en la compu *Respaldar ahora* → pasa
el `.zip` al celular → en la app del celular *Configuración → Respaldo →
Restaurar…* y elígelo.

## Si algo falla al compilar

Copia el final del error. Lo más común:
- Falta un paquete para Android (p. ej. alguna dependencia con código en C):
  se ajusta en `pyproject.toml` → `[project].dependencies`.
- "Keystore was tampered with, or password was incorrect": contraseña equivocada.
