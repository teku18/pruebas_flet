# Respaldo de ControlKraken con Google Drive (rclone)

```
ControlKraken ──zip──▶ ~/Respaldos/ControlKraken ◀──rclone (cada 15 min)──▶ Google Drive/ControlKraken
   (Configuración → Respaldo)                    sube lo tuyo / baja lo de otros equipos
```

La app solo escribe zips en una carpeta local. rclone los copia a Drive.
Así la app no guarda contraseñas ni tokens de Google.

## 1. Instalar y conectar rclone (una sola vez)

```bash
sudo apt install rclone          # o: curl https://rclone.org/install.sh | sudo bash
rclone config
```

En el asistente:

| Pregunta | Respuesta |
| --- | --- |
| `n) New remote` | `n` |
| name | `gdrive` |
| Storage | `drive` (Google Drive) |
| client_id / client_secret | Enter (vacío) |
| scope | `1` (acceso completo) o `3` (solo archivos que crea rclone) |
| service_account_file | Enter |
| Edit advanced config? | `n` |
| Use web browser to authenticate? | `y` → se abre el navegador, entras con tu cuenta y autorizas |
| Shared Drive? | `n` |
| Keep this remote? | `y`, luego `q` |

Prueba:

```bash
mkdir -p ~/Respaldos/ControlKraken
rclone mkdir gdrive:ControlKraken
rclone lsd gdrive:            # debe aparecer ControlKraken
```

## 2. Subida automática (cron)

```bash
crontab -e
```

Agrega estas dos líneas (cada 15 minutos):

```
*/15 * * * * /usr/bin/rclone copy ~/Respaldos/ControlKraken gdrive:ControlKraken --include "ControlKraken_*.zip" >> ~/Respaldos/rclone.log 2>&1
*/15 * * * * /usr/bin/rclone copy gdrive:ControlKraken ~/Respaldos/ControlKraken --include "ControlKraken_*.zip" --max-age 24h >> ~/Respaldos/rclone.log 2>&1
```

La 1.ª sube tus respaldos. La 2.ª baja los de las últimas 24 h hechos en otros
equipos: así la app puede avisarte "hay un respaldo más reciente de otro equipo".

`copy` solo copia lo nuevo y **nunca borra** en Drive. La limpieza de la app
(últimos 5 + uno por mes) aplica solo a la carpeta local; en Drive se acumulan
(pesan pocos KB). Si quieres que Drive quede igual que la carpeta, usa `sync`
en lugar de `copy` (cuidado: si borras la carpeta local, también se borra en Drive).

Subir en este momento: `rclone copy ~/Respaldos/ControlKraken gdrive:ControlKraken -P`

## 3. En la app

Configuración → Respaldo:
- **Carpeta**: `~/Respaldos/ControlKraken` (la de arriba)
- **Automático**: 2 min después de tu último cambio crea un zip
- **Respaldar ahora** / **Restaurar…**

## 4. Equipo nuevo

```bash
git clone git@github.com:teku18/pruebas_flet.git && cd pruebas_flet
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
rclone config                     # paso 1, para conectar tu Drive
rclone copy gdrive:ControlKraken ~/Respaldos/ControlKraken -P
flet run main.py                  # "Bienvenido" → Restaurar respaldo → el zip más nuevo
```

(Sin rclone: descarga el zip desde drive.google.com y elígelo al restaurar.)

## ¿Qué pasa con mis datos al actualizar la app?

```
git pull  →  abrir la app  →  ¿hay migraciones nuevas?
                                 ├─ no → abre normal
                                 └─ sí → copia en respaldos/ → migra → abre
```

- La BD y `data/` no están en git: `git pull` nunca los toca.
- Antes de migrar, la app guarda una copia en `respaldos/` (últimas 5).
- Un respaldo de una versión **anterior** se puede restaurar: se migra solo.
- Uno de una versión **más nueva** que la app se rechaza: primero `git pull`.

## Cambiar de "base de operaciones"

Un solo equipo es tu base. Para pasar la estafeta:

1. Equipo viejo: **Respaldar ahora** (y espera a que suba, o `rclone copy … -P`).
2. Equipo nuevo: al abrir la app avisa **"Respaldo de otro equipo"** →
   **Restaurar**. (Si es la primera vez: **Restaurar el más reciente**.)
3. Si en realidad sigues en este equipo: **Este equipo es mi base** y no
   vuelve a preguntar por ese respaldo.

Si ambos equipos tienen cambios, el aviso lo marca con ⚠: al restaurar, lo de
este equipo se guarda en `respaldos/` pero no se mezcla.

## Regla de oro

Un solo equipo escribe a la vez. El respaldo **no es sincronización**: si
capturas en dos equipos y restauras, lo del otro se pierde.
