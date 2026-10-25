# Notivoz

Asistente de escritorio para Windows: gestiona pendientes por cliente, notas con recordatorios en pantalla y comandos de voz que abren tus apps. Te habla al iniciar la PC y al avisarte.

Hecho con **Python**, **PySide6 (Qt)** y **SQLite**.

## Funciones

| Función | Estado |
|---|---|
| Tabla de pendientes por cliente: importancia, fecha de ingreso, estado, búsqueda y filtros | ✅ Fase 1 |
| Notas con recordatorio: alerta por encima de todo y voz que dice «Recuerda: …» | ✅ Fase 2 |
| Icono en la bandeja del sistema, inicio con Windows y lectura de pendientes por voz | 🔜 Fase 3 |
| Panel de comandos: cada frase abre una lista de aplicaciones | 🔜 Fase 4 |
| Reconocimiento de voz offline (Vosk), por ejemplo «Notivoz, modo chill» | 🔜 Fase 5 |
| Ejecutable `.exe` e instalador | 🔜 Fase 6 |

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

### Pendientes

- **Clientes** abre el administrador de clientes, donde puedes agregar, editar y eliminar. Al eliminar un cliente, sus tareas se conservan y quedan sin cliente.
- **+ Nueva tarea** o `Ctrl+N` para agregar una. El cliente se elige de la lista registrada en **Clientes**.
- La **fecha de ingreso** se elige en un calendario: haz clic en el campo, o pulsa `Espacio` / `F4`.
- Los **contadores de colores** bajo el título muestran cuántas tareas hay en cada estado. Si haces clic en uno, la tabla muestra solo ese estado; otro clic quita el filtro. Los colores son: Pendiente en azul, En proceso en naranja y Realizado en turquesa.
- **Doble clic** o `Enter` sobre una fila para editarla.
- **Clic derecho** para marcar como Pendiente / En proceso / Realizado o para eliminar.
- `Supr` elimina el pendiente seleccionado (pide confirmación).
- Clic en un encabezado para ordenar por esa columna. Un tercer clic vuelve al orden por defecto: en proceso, luego pendientes por importancia y al final los realizados.

### Notas y recordatorios

- **+ Nueva nota** para escribir una. Marca **Recordarme** y elige la fecha (calendario) y la hora (formato 24 h), o usa los atajos *En 10 min*, *En 1 hora* o *Mañana 9:00*.
- Cuando llega la hora aparece una **alerta en la esquina inferior derecha, encima de cualquier aplicación**, suena un aviso y Notivoz dice en voz alta «Recuerda: …» con el título y el texto de la nota.
- En la alerta puedes elegir **Listo** o **Posponer** (5 min, 10 min, 30 min o 1 hora).
- Si la app estaba cerrada cuando vencía un recordatorio, avisa apenas se abre, marcado como «atrasado».
- Las tarjetas muestran 🔔 con la hora del próximo aviso, ✓ *Avisada* cuando ya sonó, o *Creada* con su fecha si no tienen recordatorio.
- El filtro **Fecha** muestra las notas de un día: se usa la fecha del recordatorio o, si la nota no tiene, la de creación. La ✕ (o `Supr`) quita el filtro.
- El filtro de tipo permite ver todas, solo las próximas, las que no tienen recordatorio o las ya avisadas.
- La voz usa las voces de Windows y elige automáticamente una en español (por ejemplo *Microsoft Helena*).

> Por ahora los recordatorios solo suenan con la app abierta. En la fase 3 Notivoz quedará en la bandeja del sistema y se iniciará con Windows.

## Dónde se guardan los datos

La base de datos **no** está en el repositorio. Vive en la carpeta de datos de tu usuario:

```
%APPDATA%\Notivoz\notivoz.db
```

Para hacer una copia de seguridad, basta con copiar ese archivo. Para pruebas puedes usar otra carpeta con la variable de entorno `NOTIVOZ_DATA_DIR`.

## Estructura

```
notivoz/
├── main.py                  Punto de entrada
├── app/
│   ├── config.py            Nombre, versión y rutas de datos
│   ├── data/
│   │   ├── models.py        Tablas: clientes, pendientes, notas
│   │   └── database.py      Conexión SQLite y sesiones
│   ├── services/
│   │   ├── pendientes.py    Lógica de tareas: listar, guardar, cambiar estado, eliminar
│   │   ├── clientes.py      Lógica de clientes: crear, renombrar, eliminar
│   │   ├── notas.py         Lógica de notas y recordatorios: vencidas, posponer…
│   │   └── voz.py           Texto a voz con las voces de Windows (SAPI)
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
│       └── formato.py       Textos de fecha («Hoy 15:30», «en 10 min»)
└── requirements.txt
```
