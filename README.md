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
python main.py
```

En VS Code basta con abrir la carpeta y pulsar **F5**. La configuración «Notivoz» ya usa el entorno `.venv`.

## Uso

### Mis tareas

- **Clientes** abre el administrador de clientes, donde puedes agregar, editar y eliminar. Al eliminar un cliente, sus tareas se conservan y quedan sin cliente.
- **+ Nueva tarea** o `Ctrl+N` para agregar una. El cliente se elige de la lista registrada en **Clientes**.
- La **fecha de ingreso** se elige en un calendario: haz clic en el campo, o pulsa `Espacio` / `F4`.
- Los **contadores de colores** bajo el título muestran cuántas tareas hay en cada estado. Si haces clic en uno, la tabla muestra solo ese estado; otro clic quita el filtro. Los colores son: Pendiente en azul, En proceso en naranja y Realizado en turquesa.
- **Doble clic** o `Enter` sobre una fila para editarla.
- **Clic derecho** para marcar como Pendiente / En proceso / Realizado o para eliminar.
- `Supr` elimina el pendiente seleccionado (pide confirmación).
- Al pasar una tarea a **Realizado** se guarda su **fecha de culminación** (columna *Culminado*). Si vuelve a otro estado, la fecha se borra.
- Junto al estado *Realizado* aparece un icono **✉**: abre el **correo de tarea realizada**, con asunto y mensaje formales listos para copiar (saludo según la hora, cliente, fecha de culminación, descripción y tu firma). Tiene un botón **Copiar** para el asunto, otro para el mensaje, y **Otra versión** para cambiar las frases. No envía nada: solo prepara el texto.
- **Prioridad sugerida:** si una tarea lleva una semana esperando (dos si ya es Alta), aparece una flecha **↑** junto a su importancia. Con clic derecho → *Subir importancia* la subes un nivel.
- **🔥 Racha:** días seguidos en los que terminaste al menos una tarea. Al terminar la primera del día, Notivoz lo celebra.
- Clic derecho → **🎯 Modo enfoque en esta tarea**: eliges los minutos, la tarea pasa a *En proceso* y los recordatorios esperan hasta que termines. Al acabar, Notivoz te lo dice y pregunta (con **Sí / No**) si la marca como realizada. El tiempo restante se ve en la barra lateral; clic ahí para terminarlo antes.
- Clic en un encabezado para ordenar por esa columna. Un tercer clic vuelve al orden por defecto: en proceso, luego pendientes por importancia y al final los realizados.

### Notas y recordatorios

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
  - La **personalidad** de Notivoz (Configuración → Voz): *Formal* (trata de usted), *Amigable* o *Divertido*. Cambia las frases que dice Notivoz.
- Notivoz no se abre dos veces: si ya está en la bandeja y lo vuelves a ejecutar, solo se muestra la ventana.
- Hay un registro de eventos y errores en `%APPDATA%\Notivoz\notivoz.log`.

### Comandos de voz

- En **Comandos de voz**, **+ Nuevo comando** crea una frase (por ejemplo *modo trabajo*) y la lista de lo que abre:
  - **Apps instaladas**: la lista del menú Inicio, incluidas las de la Tienda como Spotify.
  - **Archivos** `.exe` / `.lnk`.
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
  - Reacciona al volumen de tu voz.
  - Muestra un anillo girando mientras se abren las apps.
  - Palpita mientras Notivoz dice la respuesta y luego desaparece.
  - Si no dices un comando en 5 segundos, se oculta y deja de esperarlo.
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
│   │   ├── personalidad.py  Frases de Notivoz en tres estilos (formal, amigable, divertido)
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
│       ├── recordatorios.py Alerta siempre encima y programador de avisos
│       ├── widgets.py       Campo de fecha con calendario, contadores de estado
│       ├── formato.py       Textos de fecha («Hoy 15:30», «en 10 min»)
│       ├── configuracion_view.py
│       ├── bandeja.py       Icono y menú de la bandeja del sistema
│       ├── icono.py         Icono de la app dibujado por código
│       ├── comandos_view.py Tarjetas de comandos y botón de micrófono
│       ├── comando_dialog.py  Formulario de comando y selector de apps instaladas
│       ├── burbuja.py       Burbuja flotante que reacciona a la voz
│       ├── iconos_menu.py   Iconos del menú lateral
│       ├── correo_dialog.py   Correo de tarea realizada
│       ├── rutinas_view.py    Rutinas y su formulario
│       └── productividad.py   Modo enfoque, programador de rutinas y aviso de ocio
├── requirements.txt
└── requirements-dev.txt     Herramientas de desarrollo (pyflakes)
```
