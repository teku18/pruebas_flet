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
pip install -r requirements.txt     # flet[all] trae `flet build`; y el parche de avisos
./scripts/build_apk.sh              # o: bash scripts/build_apk.sh
```

- **La primera vez tarda** (10–30 min): `flet build` descarga solo Flutter,
  el SDK de Android y Java si faltan (varios GB). Las siguientes, unos minutos.
- Pide la contraseña de la llave (no se guarda en ningún archivo).
- Versión que ves en el celular = `APP_VERSION` de `core/__init__.py`.
  Número interno (`--build-number`) = número de commits: siempre sube, que es
  lo que Android exige para aceptar una actualización. **Haz commit antes de
  generar cada APK nuevo.**
- **Avisos (desde 1.2.1):** el script aplica solo el parche de
  `flet-android-notifications`. La primera vez verás un error de
  "desugaring" y luego "aplicándolo y compilando otra vez…": es normal.
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
| Subir a Drive | rclone ✓ (automático) | «Respaldar y mandar a Drive» → eliges Google Drive (manual, avisa a los 7 días) |
| Captura / grabación | ✓ | ✓ |

**Pasar tus datos de la compu al celular:** en la compu *Respaldar ahora* (rclone
lo sube a Drive) → en el celular *Configuración → Respaldo → Restaurar…* y elige
el zip directo desde Google Drive.

**Del celular a Drive:** *Respaldar y mandar a Drive* → Google Drive → carpeta
ControlKraken (un solo botón: crea el zip y abre el selector). Así la compu lo ve en la siguiente sincronización.

## Si algo falla al compilar

Copia el final del error. Lo más común:
- Falta un paquete para Android (p. ej. alguna dependencia con código en C):
  se ajusta en `pyproject.toml` → `[project].dependencies`.
- "Keystore was tampered with, or password was incorrect": contraseña equivocada.
