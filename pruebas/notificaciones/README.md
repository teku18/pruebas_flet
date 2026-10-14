# Prueba: avisos con la app cerrada (opción A)

App mínima, **aparte de ControlKraken** (id `com.teku18.cknotifprueba`), para
saber si `flet-android-notifications` funciona con Flet 1.0 antes de meterlo
en la Agenda.

## 1. Compilar (en la compu)

```bash
cd ~/workspace_personal/pruebas_flet/pruebas/notificaciones
source ../../.venv/bin/activate
pip install flet-android-notifications==0.12.0

flet build apk -v 2>&1 | tee build1.log        # 1ª vez: crea build/flutter
flet-android-notifications-patch                # agrega receptores y desugaring
flet build apk -v 2>&1 | tee build2.log        # 2ª vez: ya con el parche
```

Si la 1ª compilación falla, igual corre el parche y la 2ª. Si la 2ª también
falla, mándame el final de `build2.log`.

El APK queda en `build/apk/`. Va firmado con la llave de pruebas (no la tuya),
por eso es otra app.

## 2. Probar en el celular

1. Instala el APK y ábrelo.
2. **1. Pedir permisos**: acepta los dos (notificaciones y alarmas/recordatorios).
3. **2. Notificación ahora**: debe aparecer una notificación. (Si no, ya sabemos
   que no sirve: anota el error que sale en la lista.)
4. **3. Programar en 2 min** → **4. Ver programadas** (deben salir 2).
5. **Cierra la app** (deslízala fuera de recientes) y bloquea el celular.
6. Espera 2–5 minutos.

## 3. Qué me cuentas

| Pregunta | Respuesta |
|---|---|
| ¿Compiló? (¿en la 1ª o la 2ª?) | |
| ¿Salió la notificación inmediata? | |
| ¿Llegó el aviso **exacto** con la app cerrada? ¿A qué hora? | |
| ¿Llegó el **inexacto**? ¿A qué hora? | |
| Marca y modelo del celular / versión de Android | |

Extra (opcional): programa otra vez, **reinicia el celular** y espera: ¿llega?
