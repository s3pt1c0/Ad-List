# Unified DNS Blocklist – 68 fuentes

Combina las **68 listas públicas** del archivo original `PI-Hole Adlist 2023.txt` en **una lista maestra de dominios**, compatible en principio con el formato de Pi-hole y utilizable como fuente de dominios para políticas que acepten listas externas de UniFi Network 11.

## Archivos

- `sources.txt`: las 68 direcciones originales de tus listas (una URL por línea).
- `scripts/build.py`: descarga HTTPS, extrae nombres de dominios, valida, elimina duplicados, ordena y genera el resultado.
- `.github/workflows/update.yml`: genera/actualiza la lista diariamente (02:17 AST) o por ejecución manual.
- `allowlist.txt`: excepciones de dominios exactos que nunca se agregarán a la lista.
- `master-blocklist.txt`: **se genera en la primera ejecución exitosa** de GitHub Actions.
- `build-report.json`: estadísticas por fuente y URLs que fallaron (también se genera al ejecutar).

## Instalación

1. Crea un **repositorio público** nuevo en GitHub, por ejemplo, `dns-master-blocklist`.
2. Copia y sube **todos los archivos y carpetas** de este ZIP manteniendo la estructura (la carpeta `.github/workflows/` es imprescindible). Se puede hacer con Git o desde la página del repositorio.
3. En **Settings → Actions → General → Workflow permissions**, selecciona **Read and write permissions** si tu repositorio no permite que el workflow escriba (para poder publicar el `.txt`).
4. En **Actions → Update Master DNS Blocklist → Run workflow**, ejecuta la primera compilación manualmente.
5. Verifica que se hayan creado `master-blocklist.txt` y `build-report.json`. Revisa `failed_sources` en el reporte; si alguna dirección dejó de funcionar, corrígela o comenta la URL en `sources.txt`.
6. Agrega al Pi-hole **solo esta lista maestra** y luego puedes retirar las 68 adlists anteriores, una vez comprobada la cobertura y resolución DNS.
7. Para UniFi Network 11, crea una Network List externa de tipo Domain e introduce la URL Raw (si la capacidad de tu equipo soporta la cantidad total de dominios).

### URL única

Reemplaza `USUARIO` por tu nombre de usuario de GitHub y `REPOSITORIO` por el nombre de tu repositorio. Si usas una rama por defecto distinta de `main`, cambia `main` por ese nombre.

```text
https://raw.githubusercontent.com/USUARIO/REPOSITORIO/main/master-blocklist.txt
```

## Actualización

GitHub Actions ejecuta el script una vez al día a las 06:17 UTC = **02:17 AST (Puerto Rico)**, sin consumir recursos del Pi-hole. Cada ejecución reemplaza el archivo si hubo cambios. El horario puede sufrir retrasos según GitHub.

### Precauciones de calidad

- Las fuentes no se han descargado ni verificado en vivo durante la preparación de este paquete. Algunas direcciones pueden estar rotas o haber cambiado de formato.
- La lista incluye **pornografía, drogas, TikTok, torrent, gambling, piracy, rastreadores, malware**, y mucho más; no es exclusivamente una lista de anuncios. Puede bloquear servicios legítimos.
- El parser acepta líneas de dominio, hosts (`0.0.0.0 dominio`) y reglas Adblock Plus de dominio (`||dominio^`). Ignora reglas específicas por ruta web y sintaxis incompatible, porque no se pueden representar fielmente como dominios DNS.
- Si menos del 75 % de las URLs funciona, se **interrumpe la publicación** y se mantiene la lista maestra anterior.
- Si una actualización reduce el número de dominios en más del 10 % respecto al archivo anterior, se **interrumpe** para evitar pérdida masiva accidental de cobertura.
- Si hay fallas aisladas, la compilación puede publicarse con cobertura parcial. Revisa siempre `build-report.json`.
- Grandes cantidades de dominios pueden superar las capacidades de memoria o límites de UniFi (dependen de gateway/firmware). No se asume compatibilidad por tamaño sin probar.
- Las listas de terceros pueden estar sujetas a licencias y condiciones de redistribución; **compruébalas antes de hacer público** un espejo agregado.
- Usa una lista de exclusiones (`allowlist.txt`) para corregir falsos positivos. Las excepciones son exactas, no cubren subdominios automáticamente.
- GitHub puede desactivar workflows programados de repositorios públicos inactivos; comprueba ocasionalmente su estado.

## Uso local y prueba

```bash
python3 scripts/build.py
```

Requiere Python 3.10+ y acceso a Internet; no requiere librerías adicionales.

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
```

## Notas sobre Pi-hole y UniFi

Pi-hole bloquea consultas **DNS**, mientras que las Network Lists externas de UniFi están destinadas a **políticas de red/firewall/routing**. No son intercambiables a nivel funcional. Si ambas herramientas consumen la misma URL, valida reglas, alcance y límites de cada una; no desactives Pi-hole hasta confirmar la alternativa.
