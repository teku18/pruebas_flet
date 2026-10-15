# Prueba: SSH (paramiko) dentro del APK

App mínima, **aparte de ControlKraken** (id `com.teku18.cksshprueba`), para
saber si SSH funciona en el celular antes de construir el monitor de
servidores (Kraken Tools 1.7.0).

El riesgo: paramiko usa librerías con partes en C (cryptography, bcrypt,
PyNaCl). Flet dice tenerlas compiladas para Android; esta prueba lo confirma.

## 1. Compilar (en la compu)

```bash
cd ~/workspace_personal/pruebas_flet/pruebas/ssh
source ../../.venv/bin/activate
flet build apk -v 2>&1 | tee build.log
```

Si falla, mándame el final de `build.log` (las últimas ~60 líneas).
El APK queda en `build/apk/`.

## 2. Probar en el celular

1. Instala el APK y ábrelo.
2. Arriba sale **"Librerías"**: todas deben tener ✓. Si alguna sale con ✗,
   mándame captura (ya con eso sabemos la respuesta).
3. Escribe un servidor al que entres por SSH (uno de un cliente o tu PC con
   `openssh-server`), usuario y contraseña → **Conectar y leer el servidor**.
   Solo corre comandos de lectura: `uname`, `uptime`, `free`, `df`,
   `systemctl is-active`. **No cambia nada.** La contraseña no se guarda.
4. Prueba con Wi-Fi y con datos móviles.

## 3. Qué me cuentas

| Pregunta | Respuesta |
|---|---|
| ¿Compiló? | |
| ¿Las 6 líneas de "Librerías" con ✓? | |
| ¿Conectó? ¿En cuántos ms? | |
| ¿Salieron memoria, disco y servicios? | |
