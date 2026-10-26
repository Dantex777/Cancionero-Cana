# Cancionero Caná — publicación en Streamlit Community Cloud

## Contenido (sube estos archivos DESCOMPRIMIDOS al repositorio)

- `app.py` — aplicación Streamlit v0.3.2.
- `musica.py` — motor de lectura musical y transposición.
- `conexion_notion.py` — lectura de la API de Notion.
- `requirements.txt` — dependencias.
- `.gitignore` — evita subir credenciales por accidente.

No contiene claves privadas, contenido musical exportado ni archivos locales.
**Jamás subas `.env`, `.venv` o el token de Notion a GitHub.**

## 1. Crear repositorio en GitHub

En https://github.com/new inicia sesión y crea un repositorio llamado `cancionero-cana`, preferiblemente público si quieres que el código sea accesible (la app podrá ser pública). Si eliges repositorio privado, Streamlit necesita permisos adicionales.
Abre el repositorio, elige `Add file` > `Upload files`, arrastra los cinco archivos de este paquete descomprimido, y usa `Commit changes`.

## 2. Publicar app

Entra en https://share.streamlit.io, conecta tu cuenta de GitHub, elige `Create app` > `Yup, I have an app`.
Elige tu repositorio, rama `main` y ruta principal `app.py`.

Antes de desplegar: `Advanced settings` > `Secrets`. Pega este TOML reemplazando el valor *solo allí*:

    NOTION_API_TOKEN = "tu_token_privado_de_notion"

Guarda los ajustes y pulsa `Deploy`.
Si eliges versión de Python, puedes usar 3.12 (compatible con este proyecto). No es necesario copiar tu Python 3.14 local.

## 3. Comprobación

Abre la URL `https://[subdominio].streamlit.app` asignada por Streamlit.
Comprueba: aparecen tus canciones con Estado = Publico, acordes en amarillo, transposición y filtro.
Si no hay canciones, comprueba permiso de lectura de Notion para `Canciones Caná`, secreto `NOTION_API_TOKEN` y los logs de Streamlit. El programa solo necesita lectura y nunca edita Notion.

## 4. Actualizar

- Nuevo canto en Notion: actualiza la app desde el botón `Actualizar canciones` (o espera expiración de caché).
- Cambio del código: sube la nueva versión del archivo a GitHub y Streamlit actualizará la app.
- Publicación pública significa que los visitantes podrán leer los cantos. Asegúrate de contar con permisos para difundir letras y arreglos musicales de terceros.

Referencia: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
