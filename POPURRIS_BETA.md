# Popurrís Caná · v0.5.0 beta

Esta rama es experimental. No modifica la base existente **Canciones Caná**.

## Prototipo ya disponible
- Menú lateral **Crear Popurrí**.
- Añadir y repetir cantos, reordenar y quitar.
- Tres modos: **Originales**, **Unificar tono** y **Personalizado**.
- **−1 / +1** en cada canto. Al pulsarlos, el modo cambia a **Personalizado** y conserva los tonos actuales de los demás.
- Una sola zona de lectura con títulos, divisores y Auto Scroll continuo.
- Guardar una copia local como JSON e importarla.
- Guardar y abrir popurrís compartidos en una **segunda base de Notion**, sólo si se configura el acceso correspondiente.

## Segunda base en Notion
Crea una **base de datos nueva** llamada `Popurrís Caná` (distinta de `Canciones Caná`). Necesita exactamente estas propiedades:

| Propiedad | Tipo |
|---|---|
| Nombre | Título (Title) |
| Datos | Texto (Rich text) |

En las opciones de Notion, comparte **únicamente** esa base con una integración separada (por ejemplo `Cana Popurris API`) con permisos **Read content** y **Insert content**. No concedas acceso de escritura sobre la base original de canciones.

En la configuración **Secrets** de la app **de pruebas** de Streamlit agrega estas claves, utilizando sus valores REALES:

```toml
NOTION_POPURRIS_SOURCE_ID = "id-de-la-fuente-de-datos"
NOTION_POPURRIS_TOKEN = "ntn_token-de-la-integracion-separada"
POPURRIS_ADMIN_PASSWORD = "una-clave-larga-y-privada"
```

**El ID de la fuente de datos no es necesariamente igual al ID de la base de datos** en la API moderna de Notion. Consíguelo desde el portal de desarrollo o recupera la fuente desde la API. Nunca compartas tokens ni contraseñas en capturas, chats o GitHub.

La app pública es accesible para todos: cualquier visitante puede consultar los popurrís guardados. Sólo quien introduzca la clave administrativa podrá guardar nuevos. Este sistema es una protección básica para un grupo pequeño; si se quisiera edición por múltiples usuarios o distintos roles, lo recomendable es autenticación por usuario.

Si no configuras estas credenciales, el Modo Popurrí funciona sin Notion y permite importar/exportar un JSON local. Las sesiones de Streamlit pueden reiniciarse: una lista que no se haya exportado o guardado se perderá.

## Pruebas antes de fusionar
1. Añade canciones en Dm y Am.
2. En **Originales**, verifica que cada una conserve su tono.
3. En **Unificar tono**, elige Bm; comprueba que Dm pasa a Bm (−3) y Am a Bm (+2).
4. Pulsa **+1** sólo en una canción: ahora aparece **Personalizado**, manteniendo sin cambios la otra.
5. Reordena y repite una canción; comprueba títulos, líneas divisorias y Auto Scroll.
6. Si configuraste Notion, guarda el popurrí, recarga el navegador, actualiza la lista y vuelve a abrirlo.
7. Verifica el resultado en iPhone y Android. No fusiones con `main` hasta aprobar el funcionamiento.

## Restricciones
La transposición cambia las notas, no los modos. **Unificar tono** no transforma automáticamente una canción mayor en menor o viceversa. Canciones con modo incompatible permanecen en el tono original y se advierte al músico.
