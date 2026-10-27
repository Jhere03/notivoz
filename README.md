# Notivoz

Asistente de escritorio para Windows: gestiona pendientes por cliente, notas con recordatorios en pantalla y comandos de voz que abren tus apps. Te habla al iniciar la PC y al avisarte.

Hecho con **Python**, **PySide6 (Qt)** y **SQLite**.

## Funciones

| Función | Estado |
|---|---|
| Tabla de pendientes por cliente: importancia, fecha de ingreso, estado, búsqueda y filtros | ✅ Fase 1 |
| Notas con recordatorio: alerta por encima de todo y voz que dice «Recuerda: …» | ✅ Fase 2 |
| Icono en la bandeja del sistema, inicio con Windows y lectura de pendientes por voz | ✅ Fase 3 |
| Panel de comandos: cada frase abre una lista de aplicaciones | ✅ Fase 4 |
| Reconocimiento de voz offline (Vosk), por ejemplo «Notivoz, modo trabajo» | ✅ Fase 5 |
| Personalidad (formal, amigable o divertido) y comandos que también cierran | ✅ |
| Correo de «tarea realizada» listo para copiar, fecha de culminación | ✅ |
| Rutinas por horario, modo enfoque, racha, prioridad sugerida, resumen al apagar y aviso de ocio | ✅ |
| Ejecutable `.exe` e instalador | 🔜 Fase 6 |
| Sincronización con el celular | 🔜 Más adelante |

## Requisitos

- Windows 10 u 11
- Python 3.15 (o 3.14)

## Puesta en marcha

```bash
git clone git@github.com:Jhere03/notivoz.git
cd notivoz
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install --no-deps -r requirements-ia.txt
python main.py
```

En VS Code basta con abrir la carpeta y pulsar **F5**. La configuración «Notivoz» ya usa el entorno `.venv`.

## Instalar Notivoz (sin programar)

1. Descarga `Notivoz-Setup-X.Y.Z.exe` desde [Releases](https://github.com/Jhere03/notivoz/releases).
2. Ábrelo. Si Windows muestra «Windows protegió su PC», pulsa **Más información → Ejecutar de todas formas** (el instalador aún no tiene firma digital).
3. Sigue el asistente. Se instala solo para tu usuario, sin permisos de administrador. Al abrir Notivoz por primera vez prepara la voz solo (descarga ~500 MB, una vez).
4. Para la IA: **Configuración → Asistente con IA**, pega tu clave de Anthropic y activa el asistente.

**Actualizaciones:** cuando hay una versión nueva, en el menú lateral aparece «Hay una nueva actualización». Un clic la descarga (verificando su huella SHA-256), se instala y Notivoz se vuelve a abrir. Tus tareas, notas y ajustes no se tocan.

## Publicar una versión (desarrollo)

Requisitos, una vez: `pip install -r requirements-dev.txt`, Inno Setup 6 (`winget install JRSoftware.InnoSetup`) y GitHub CLI con sesión iniciada (`winget install GitHub.cli` y luego `gh auth login`).

1. Sube `APP_VERSION` en `app/config.py` (por ejemplo `0.1.1`) en tu rama y haz el merge a `master`.
2. En `master`, actualizado y sin cambios pendientes:

```bash
.venv\Scripts\python empaquetado\publicar.py "Qué cambió en esta versión"
```

Construye `Notivoz.exe` y el instalador, y crea el Release con el instalador y su huella. Solo para construir, sin publicar: `.venv\Scripts\python empaquetado\construir.py` (deja el instalador en `dist\instalador`).

## Uso

### Mis tareas

- **Clientes** abre el administrador de clientes, donde puedes agregar, editar y eliminar. Al eliminar un cliente, sus tareas se conservan y quedan sin cliente.
- **+ Nueva tarea** o `Ctrl+N` para agregar una. El cliente se elige de la lista registrada en **Clientes**.
- La **fecha de ingreso** se elige en un calendario: haz clic en el campo, o pulsa `Espacio` / `F4`.
- Los **contadores de colores** bajo el título muestran cuántas tareas hay en cada estado. Si haces clic en uno, la tabla muestra solo ese estado; otro clic quita el filtro. Los colores son: Pendiente en azul, En proceso en naranja y Realizado en turquesa.
- **Doble clic** o `Enter` sobre una fila para editarla.
- El **ojo** 👁 al final de cada fila muestra la tarea completa sin editarla: la ventana se ajusta al texto para leerlo todo de una vez (solo si no cabe en la pantalla aparece el desplazamiento). Desde ahí, **Editar** abre el formulario.
- **Clic derecho** para marcar como Pendiente / En proceso / Realizado o para eliminar.
- `Supr` elimina el pendiente seleccionado (pide confirmación).
- Al pasar una tarea a **Realizado** se guarda su **fecha de culminación** (columna *Culminado*). Si vuelve a otro estado, la fecha se borra.
- Junto al estado *Realizado* aparece un icono **✉**: abre el **correo de tarea realizada**, con asunto y mensaje formales listos para copiar (saludo según la hora, cliente, fecha de culminación, descripción y tu firma). Tiene un botón **Copiar** para el asunto, otro para el mensaje, y **Otra versión** para cambiar las frases. No envía nada: solo prepara el texto.
- **Prioridad sugerida:** si una tarea lleva una semana esperando (dos si ya es Alta), aparece una flecha **↑** junto a su importancia. Con clic derecho → *Subir importancia* la subes un nivel.
- **🔥 Racha:** días seguidos en los que terminaste al menos una tarea. Al terminar la primera del día, Notivoz lo celebra.
- Clic derecho → **🎯 Modo enfoque en esta tarea**: eliges los minutos, la tarea pasa a *En proceso* y los recordatorios esperan hasta que termines. Al acabar, Notivoz te lo dice y pregunta (con **Sí / No**) si la marca como realizada. El tiempo restante se ve en la barra lateral; clic ahí para terminarlo antes.
- Clic en un encabezado para ordenar por esa columna. Un tercer clic vuelve al orden por defecto: en proceso, luego pendientes por importancia y al final los realizados.

### Notas y recordatorios

- El **ojo** 👁 de cada nota la muestra completa, sin editarla, en una ventana que se ajusta a su texto.
- **+ Nueva nota** para escribir una. Marca **Recordarme** y elige la fecha (calendario) y la hora (formato 24 h), o usa los atajos *En 10 min*, *En 1 hora* o *Mañana 9:00*.
- Cuando llega la hora aparece una **alerta en la esquina inferior derecha, encima de cualquier aplicación**, suena un aviso y Notivoz dice en voz alta «Recuerda: …» con el título y el texto de la nota.
- En la alerta puedes elegir **Listo** o **Posponer** (5 min, 10 min, 30 min o 1 hora).
- Si la app estaba cerrada cuando vencía un recordatorio, avisa apenas se abre, marcado como «atrasado».
- Las tarjetas muestran 🔔 con la hora del próximo aviso, ✓ *Avisada* cuando ya sonó, o *Creada* con su fecha si no tienen recordatorio.
- El filtro **Fecha** muestra las notas de un día: se usa la fecha del recordatorio o, si la nota no tiene, la de creación. La ✕ (o `Supr`) quita el filtro.
- El filtro de tipo permite ver todas, solo las próximas, las que no tienen recordatorio o las ya avisadas.
- **Voz:**
  - Por defecto usa **voces neuronales de Microsoft** (edge-tts), muy naturales: Camila (Perú), Dalia (México), Elvira (España) y otras. Se eligen en **Configuración → Voz**.
  - Estas voces **necesitan internet**, porque el texto a leer se envía al servicio de voz de Microsoft Edge.
  - Sin conexión, Notivoz usa automáticamente la voz de Windows en español (*Microsoft Helena*).
  - Los audios ya generados se guardan en `%APPDATA%\Notivoz\voz_cache` (máximo 300), así las frases repetidas suenan al instante y también sin internet.
  - Si prefieres no usar internet para la voz, elige **«Voz de Windows»**.

### Asistente con IA

- Di «Notivoz»: aparece la burbuja unos 3 segundos («Presióname para hablar»). **Presiónala** (o pulsa tu tecla para hablar) y pide lo que quieras con tus palabras: «recuérdame pagar el internet el viernes a las 9», «¿qué tengo pendiente con ACME?», «pasa a realizado lo del contrato», «abre Spotify», «activa el modo relax».
  - Mientras hablas, la burbuja pone carita de escuchar (abre la boca con tu voz y salen ondas) y la nube dice «Escuchándote…». Al callarte pasa sola a «Procesando…» (no hace falta presionar nada): mira a los lados, se estira como gelatina y giran tres lucecitas, sin desaparecer hasta que Notivoz responde. Con la personalidad Peruanazo dice «Ladra…» y «Chambeando…».
  - **Tecla para hablar** (Configuración → Comandos de voz → Tecla): elige una tecla, por ejemplo «V». Tras decir «Notivoz», o mientras procesa, púlsala una vez en vez de presionar la burbuja. Solo se usa mientras la burbuja está a la vista; el resto del tiempo la tecla escribe normal.
  - Mientras procesa no te escucha. Si quieres agregar algo, presiónala otra vez y dilo: se suma a lo anterior y responde todo junto.
  - La respuesta se lee en la nube mientras Notivoz habla. Después la burbuja queda unos segundos: presiónala para seguir la conversación.
- Tu voz se convierte en texto **en tu equipo** con Whisper (sin internet). Solo el texto del pedido va a Claude Haiku (Anthropic), que decide qué hacer con las herramientas de Notivoz.
- Respuestas cortas: al crear, editar o eliminar algo no lo describe, solo confirma con una frase que va variando según su personalidad («Tarea registrada correctamente.», «¡Listo! Tarea creada.», «¡Ya está, causa! Tarea anotada al toque.»). Esas frases ya tienen su voz preparada, así que suenan al instante, y nunca repite la misma dos veces seguidas.
- Cuando termina de **hacer** algo (crear, editar, eliminar, abrir una app o un modo…) y no le vuelves a hablar, antes de ocultarse la burbuja se despide con una carita que va cambiando: sonrisa, guiño, lengua afuera, ojos de estrella, risa o sonrojo. Si solo conversaste o consultaste, o la acción no se pudo hacer, no hay carita. Un «gracias» u «ok» por voz se responde igual, con una carita y sin hablar.
- En **Chateemos**, la confirmación de lo que hizo lleva un emoji de su personalidad, y un «gracias» se responde con un emoji.
- Para callarla mientras habla, presiónala o di «espera» o «silencio».
- **Rapidez:** al oír «Notivoz», mientras decides si la tocas, ya deja lista la conexión con la IA. Un pedido suele tardar 1 a 2 segundos; si la IA no responde en 9 segundos, se corta y se reintenta una vez.
- Actúa sin pedir confirmación cuando te entendió (crear, editar, recordatorios, eliminar); solo pregunta si algo no quedó claro. Entiende nombres que suenan parecido («Bento» → tu cliente «Dento», «F» → «EFE»).
- Puede leer toda la app (correos de tareas realizadas, rutinas, configuración) y abrir su ventana: «Notivoz, ábrete en mis notas».
- Si haces pausas para pensar («…y», «o sea…», «este…»), Notivoz espera a que termines antes de responder.
- **Apagar o reiniciar la PC**: «Notivoz, apaga mi PC porfa, en unos 5 minutos», «reiníciala en media hora», «apágala a las 8:50». Si no dices cuándo, te pregunta si ahora o a qué hora.
  - Una hora sin «de la mañana» o «de la noche» se toma como la próxima vez que llega (a las 7 p. m., «8:50» es 8:50 de la noche), y Notivoz siempre te dice la hora exacta que entendió. Hasta 24 horas después.
  - Mientras está programado, la cuenta regresiva se ve en la barra lateral (abajo, sobre la versión); clic ahí para cancelarlo. También puedes decir «cancela el apagado».
  - Un minuto antes aparece un aviso encima de todo con **Cancelar apagado** y **Apagar ya**, y Notivoz te lo dice.
  - **«Apágala ahora»**: primero pregunta «¿Seguro que la apago ahora? Guarda tu trabajo.». Presiona la burbuja y di «sí» (o escríbelo en Chateemos): se despide según su personalidad («¡Chau, causa! Nos vemos al toque.») y apaga apenas termina de hablar, sin el aviso de un minuto. Con «no», la deja encendida.
  - No fuerza: los programas con cambios sin guardar te pedirán guardar. Solo lo hace si tú lo pides con tus palabras (un texto guardado en una nota nunca puede apagar la PC). Si cierras Notivoz, el apagado programado se cancela.
- Solo responde sobre Notivoz; cualquier otra pregunta la rechaza (con su personalidad).
- **Puesta en marcha** (Configuración → Asistente con IA):
  1. Crea una clave en [console.anthropic.com](https://console.anthropic.com) → API Keys (carga crédito y pon un límite de gasto mensual).
  2. Pégala en Notivoz y pulsa «Guardar clave»: se comprueba sin gastar y se guarda cifrada en el Administrador de credenciales de Windows.
  3. Descarga Whisper (≈460 MB, una sola vez) y marca «Activar el asistente con IA».
- **Seguridad:**
  - Notivoz no trae ninguna clave: cada persona usa la suya, y nunca se guarda en archivos, en la base de datos ni en el registro de la app.
  - Las peticiones solo van a `api.anthropic.com` (fijado en el código).
  - La IA solo puede usar una lista cerrada de acciones de Notivoz, y cada dato se valida otra vez antes de ejecutarse.
  - **Eliminar es inmediato, pero solo si tú lo pediste** en ese mismo pedido («elimina», «borra»…): un texto guardado en una nota nunca puede ordenar borrar. Lo eliminado se recupera unos minutos con el botón «Deshacer» o diciendo «deshaz eso».
  - Hay un máximo de cambios por pedido. Solo abre apps del menú Inicio y sin argumentos: puede abrir una consola, pero nunca escribe ni ejecuta nada en ella. Nunca abre desinstaladores ni el editor del registro.
  - Al cerrar una app comprueba que de verdad se cerró; forzar el cierre (podría perder cambios sin guardar) solo lo hace si tú lo confirmas.
  - El modelo de Whisper se descarga de una versión fija y se verifica con su huella SHA-256.
- **Límite de uso (beta):** 1 USD al mes, fijo. Al llegar, Notivoz deja de usar la IA hasta el mes siguiente; los comandos de voz siguen funcionando.

### Chateemos

- Escríbele a Notivoz lo mismo que le dirías por voz. Es el mismo asistente (mismas acciones, límites y seguridad) y comparte el límite de uso mensual.

### Apariencia

- En **Configuración → Apariencia** eliges entre tres temas, que se aplican al instante:
  - **Oscuro** (predeterminado).
  - **Claro**: fondos blancos y botones negros, con el mismo morado.
  - **Translúcido**: efecto acrílico de Windows 11; deja ver, desenfocado, lo que hay detrás de la ventana. Cuando la ventana no está activa, Windows la muestra opaca. Requiere Windows 11.
- Los cambios de sección, los diálogos y las tarjetas que se guardan o eliminan se animan, y al crear, editar o eliminar aparece un aviso breve en la parte inferior.

### Bandeja e inicio con Windows

- Notivoz vive en la **bandeja del sistema**, junto al reloj. Al cerrar la ventana sigue funcionando ahí y los recordatorios siguen sonando.
  - Clic en el icono abre la ventana.
  - Clic derecho muestra: Nueva tarea, Nueva nota, leeme, Resumen del día y **Salir de Notivoz**.
- En **Configuración** puedes activar:
  - **Iniciar con Windows.** Se guarda en el registro del usuario (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`), sin permisos de administrador.
  - **Arrancar oculto en la bandeja.**
  - **Leer en voz alta** cuántas tareas tienes pendientes y en proceso, y de qué cliente (sin títulos ni descripciones), y los recordatorios de hoy. Por ejemplo: «Buenos días, Erick. Tienes 4 tareas pendientes: 2 de EFE, 1 de Acme SAC y 1 sin cliente. Y 1 en proceso de EFE.».
  - Tu nombre para el saludo, la velocidad y el volumen de la voz, y un botón para probarla.
  - La **personalidad** de Notivoz (Configuración → Voz): *Formal* (serio, trata de usted), *Amigable* (cálido y con energía, sin jerga), *Divertido* (alegre y bromista, sin jerga) o *Peruanazo* (con harta jerga peruana que va variando: «causa», «batería», «cholo», «bro», «chévere», «bacán», «paja», «al toque»…). Cambia las frases que dice Notivoz y cómo responde el asistente.
- Notivoz no se abre dos veces: si ya está en la bandeja y lo vuelves a ejecutar, solo se muestra la ventana.
- Hay un registro de eventos y errores en `%APPDATA%\Notivoz\notivoz.log`.

### Comandos de voz

- En **Comandos de voz**, **+ Nuevo comando** crea una frase (por ejemplo *modo trabajo*) y la lista de lo que abre:
  - **Apps instaladas**: la lista del menú Inicio, incluidas las de la Tienda como Spotify.
  - **Programas** `.exe` / `.lnk`.
  - **Archivos** de tu PC (Excel, PDF, Word, imágenes…): se abren con su programa predeterminado, como al darles doble clic.
  - **Webs o enlaces** (`https://…`, `steam://…`).
  - Las apps se abren en el orden de la lista; puedes arrastrarlas para reordenarlas.
- Cada comando tiene una **respuesta** que Notivoz dice cuando **todas** las apps terminaron de abrir. Si no escribes una, la arma según tu **personalidad** y el tipo de modo: «¡A chambear, Erick!» para un modo de trabajo, «¡A relajarse!» para uno de ocio…
- **■ Cerrar** (o «Notivoz, **cierra** / **termina** / **apaga** modo relax») cierra lo que el comando abrió, como al pulsar la X: nunca fuerza, así no se pierde nada sin guardar. Solo cierra los programas que el propio comando abrió; las webs no, para no cerrarte el navegador.
- **▶ Ejecutar** abre el comando sin hablar. El botón **🎙 Activar micrófono** enciende la escucha; queda recordada para la próxima vez.
- Para usarlo por voz:
  - Di **«Notivoz, modo trabajo»**.
  - O di solo **«Notivoz»**, espera el pitido y di la frase dentro de los 5 segundos siguientes.
  - Todo comando empieza siempre con «Notivoz»: sin esa palabra no se ejecuta nada.
- **Burbuja de voz:** al decir «Notivoz» aparece una burbuja a la derecha de la pantalla, encima de cualquier aplicación y aunque Notivoz esté cerrado en la bandeja.
  - Con el asistente con IA activo, presiónala para hablarle (ver *Asistente con IA*).
  - Reacciona al volumen de tu voz mientras te escucha.
  - Muestra un anillo girando mientras procesa o se abren las apps, y no desaparece hasta terminar.
  - Palpita mientras Notivoz dice la respuesta y luego desaparece.
- **Reconocimiento offline (Vosk):**
  - Se descarga una vez un modelo en español de unos 39 MB, desde **Configuración → Comandos de voz**.
  - El audio del micrófono **nunca sale de tu PC**.
  - El reconocedor solo puede "oír" la palabra de activación, tus frases y algunas palabras comunes de relleno. Así una conversación normal no dispara comandos.
  - Mientras Notivoz habla, no escucha, para no activarse con su propia voz.
- Las frases deben usar palabras en español que el modelo conozca. Si alguna no la conoce, el formulario te avisa al guardar.
- En Configuración se elige el **micrófono**. Con **🎙 Probar micrófono** oyes tu voz con 1 segundo de retraso, para comprobar que funciona. La prueba termina con **Terminar prueba**, al cambiar de vista o al cerrar la app.

### Rutinas

En **Rutinas**, **+ Nueva rutina** programa algo para ciertos días y una hora:

- **Ejecutar un comando** (por ejemplo, de lunes a viernes a las 9:00, «modo trabajo»).
- **Leer mis pendientes**.
- **Leer el resumen del día**.

Si la PC estaba apagada a esa hora, la rutina se hace al encenderla, siempre que no haya pasado más de una hora. **▶ Probar** la ejecuta al momento.

### Productividad (Configuración)

- **Celebrar la racha** al terminar la primera tarea del día.
- **Resumen del día al apagar la PC:** «Hoy cerraste 4 tareas, tienes 2 en proceso…». Windows muestra «Notivoz está leyendo tu resumen» unos segundos; puedes apagar igual.
- **Aviso de ocio** (desactivado al inicio): si en tu horario de trabajo pasas a una app de ocio (Steam, Spotify…), Notivoz te recuerda tu tarea más importante, como mucho una vez cada 30 minutos. Eliges los días, las horas y las apps (también desde las que tengas abiertas).

## Dónde se guardan los datos

La base de datos **no** está en el repositorio. Vive en la carpeta de datos de tu usuario:

```
%APPDATA%\Notivoz\notivoz.db
```

Para hacer una copia de seguridad, basta con copiar ese archivo. Para pruebas puedes usar otra carpeta con la variable de entorno `NOTIVOZ_DATA_DIR`.

Las columnas nuevas se agregan solas a una base de datos existente al abrir la app (migración en `app/data/database.py`), sin perder datos.

## Estructura

```
notivoz/
├── main.py                  Punto de entrada
├── app/
│   ├── config.py            Nombre, versión y rutas de datos
│   ├── data/
│   │   ├── models.py        Tablas: clientes, pendientes, notas, ajustes, comandos, rutinas
│   │   └── database.py      Conexión SQLite, sesiones y migraciones de columnas
│   ├── services/
│   │   ├── pendientes.py    Lógica de tareas: listar, guardar, cambiar estado, eliminar
│   │   ├── clientes.py      Lógica de clientes: crear, renombrar, eliminar
│   │   ├── notas.py         Lógica de notas y recordatorios: vencidas, posponer…
│   │   ├── voz.py           Texto a voz: voces neuronales (edge-tts) con respaldo SAPI
│   │   ├── saludo.py        Textos que se leen: saludo al iniciar y resumen del día
│   │   ├── apagado.py       Apagar o reiniciar la PC a una hora (sin forzar)
│   │   ├── personalidad.py  Frases de Notivoz en cuatro estilos (formal, amigable, divertido, peruanazo)
│   │   ├── redaccion.py     Correo de tarea realizada y fechas en español
│   │   ├── ajustes.py       Preferencias guardadas en la BD
│   │   ├── inicio_windows.py  Inicio automático (registro Run)
│   │   ├── comandos.py      Comandos de voz: guardar, ejecutar y anunciar
│   │   ├── lanzador.py      Abre apps/enlaces y espera a que estén listas
│   │   ├── escucha.py       Reconocimiento de voz offline (Vosk) y palabra de activación
│   │   ├── modelo_voz.py    Descarga del modelo de Vosk en español
│   │   ├── microfono.py     Nivel de voz y prueba de micrófono con eco retrasado
│   │   └── rutinas.py       Rutinas por horario
│   └── ui/
│       ├── theme.py         Colores y estilos (tema oscuro)
│       ├── main_window.py   Ventana con barra lateral
│       ├── pendientes_view.py
│       ├── pendientes_model.py
│       ├── pendiente_dialog.py
│       ├── clientes_dialog.py
│       ├── notas_view.py    Tarjetas de notas
│       ├── nota_dialog.py
│       ├── ver_dialog.py    Ver una tarea o nota completa, sin editarla
│       ├── apagado_ui.py    Cuenta regresiva y aviso del apagado programado
│       ├── recordatorios.py Alerta siempre encima y programador de avisos
│       ├── widgets.py       Campo de fecha con calendario, contadores de estado
│       ├── formato.py       Textos de fecha («Hoy 15:30», «en 10 min»)
│       ├── configuracion_view.py
│       ├── bandeja.py       Icono y menú de la bandeja del sistema
│       ├── icono.py         Icono de la app dibujado por código
│       ├── comandos_view.py Tarjetas de comandos y botón de micrófono
│       ├── comando_dialog.py  Formulario de comando y selector de apps instaladas
│       ├── burbuja.py       Burbuja flotante que reacciona a la voz
│       ├── tecla_hablar.py  Tecla para hablar (en vez de presionar la burbuja)
│       ├── iconos_menu.py   Iconos del menú lateral
│       ├── correo_dialog.py   Correo de tarea realizada
│       ├── rutinas_view.py    Rutinas y su formulario
│       └── productividad.py   Modo enfoque, programador de rutinas y aviso de ocio
├── requirements.txt
└── requirements-dev.txt     Herramientas de desarrollo (pyflakes)
```
