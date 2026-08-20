# Hermes Commerce Agent

Distribución de Hermes Agent especializada en inteligencia comercial para productos de hardware.

La versión `0.1.0` está diseñada para investigar mercados, comparar canales y recomendar el siguiente paso. Todavía no publica productos, no compra, no cambia precios y no gasta dinero.

## La idea en una frase

Hermes Agent es el motor. Un perfil es una instancia aislada del agente. Este repositorio es la plantilla versionada que instala nuestro perfil comercial.

```text
Hermes Agent (motor)
        │
        └── perfil commerce-test (agente aislado)
                │
                ├── SOUL.md       → quién es
                ├── config.yaml   → cómo se ejecuta
                ├── skills/       → cómo hace cada trabajo
                └── knowledge/    → datos de productos
```

## Cómo funciona Hermes Agent en general

Hermes combina un modelo de lenguaje con identidad, configuración, memoria, skills y herramientas.

```text
Petición del usuario
        ↓
Hermes carga el perfil seleccionado
        ↓
SOUL.md define la identidad y los límites
        ↓
El modelo entiende la petición
        ↓
Hermes carga una skill relevante cuando hace falta
        ↓
La skill indica el procedimiento
        ↓
Las herramientas disponibles ejecutan búsquedas o acciones
        ↓
Hermes devuelve el resultado y conserva el estado del perfil
```

Los conceptos que más se confunden son estos:

| Concepto | Qué es | Qué no es |
| --- | --- | --- |
| Hermes Agent | El programa que ejecuta el agente | Este repositorio |
| Perfil | Un agente aislado con configuración, skills, memoria y sesiones propias | Una carpeta de proyecto o un sandbox |
| Distribución | Un repositorio Git que permite instalar y actualizar un perfil | Un proceso que se esté ejecutando |
| Skill | Instrucciones que enseñan al agente a realizar un trabajo | Una API o una herramienta de búsqueda |
| Herramienta | Capacidad real para buscar, navegar, ejecutar comandos o llamar servicios | Las instrucciones de una skill |
| `knowledge/` | Datos propios que distribuimos con el agente | Memoria automática ni contexto cargado siempre |
| Memoria | Información aprendida y conservada entre sesiones | El catálogo estático de productos |

Una skill puede decir «busca competidores en Internet», pero Hermes solo podrá hacerlo si el perfil dispone de una herramienta de búsqueda configurada. La skill define el método; la herramienta aporta la capacidad.

## Qué es un perfil y por qué usamos `commerce-test`

Cada perfil tiene su propio directorio de Hermes, con su propia configuración, identidad, memoria, sesiones, skills y credenciales. Esto permite tener varios agentes en la misma máquina sin mezclar su estado.

Nuestro objetivo es mantener esta separación:

```text
default        → tu Hermes actual
commerce-test  → el agente comercial que estamos construyendo
```

Instalar `commerce-test` no cambia automáticamente el perfil activo. Para probarlo de forma segura usaremos siempre `-p commerce-test`:

```bash
hermes -p commerce-test chat
```

El perfil `default` solo cambiaría si ejecutásemos expresamente:

```bash
hermes profile use commerce-test
```

No necesitamos hacerlo para las pruebas.

## Este repositorio, archivo por archivo

```text
hermes_agent/
├── distribution.yaml
├── SOUL.md
├── config.yaml
├── README.md
├── knowledge/
│   └── products/
│       └── rtx-pro-6000-server.yaml
└── skills/
    └── market-intelligence/
        └── SKILL.md
```

### `distribution.yaml`

Es el manifiesto de la distribución. No configura el razonamiento del agente; le dice al instalador qué paquete es y qué archivos pertenecen a él.

```yaml
name: hermes-commerce-agent
version: 0.1.0
hermes_requires: ">=0.14.0"

distribution_owned:
  - distribution.yaml
  - SOUL.md
  - config.yaml
  - skills/
  - knowledge/
```

En nuestro caso, `distribution_owned` incluye `knowledge/` porque no forma parte de las rutas predeterminadas de una distribución. Al instalar o actualizar el perfil, Hermes copiará esas rutas desde GitHub.

Como hemos definido explícitamente la lista completa, solo esas rutas son propiedad de la distribución. `README.md` sirve como documentación en GitHub, pero no se instala dentro del perfil.

### `SOUL.md`

Define quién es el agente, su misión, su forma de comunicarse y sus límites generales. Hermes lo carga al iniciar una sesión como identidad principal.

Nuestro `SOUL.md` convierte el perfil en un operador de inteligencia comercial para hardware y le exige:

- trabajar con evidencia;
- diferenciar hechos, señales, estimaciones e hipótesis;
- optimizar para rentabilidad sostenible;
- solicitar autorización antes de gastar, publicar o modificar operaciones comerciales;
- no inventar especificaciones, stock, garantías ni precios.

`SOUL.md` orienta al modelo, pero no sustituye los controles técnicos de permisos o sandboxing.

### `config.yaml`

Contiene la configuración técnica no secreta del perfil: modelo, proveedor, terminal, herramientas, gateway, memoria, compresión y otros ajustes.

Ahora mismo contiene únicamente:

```yaml
{}
```

Esto es intencionado. Significa que esta distribución todavía no impone ninguna configuración técnica propia. Hermes resolverá lo no especificado mediante sus valores predeterminados, pero el nuevo perfil seguirá necesitando un modelo/proveedor autenticado para poder conversar y herramientas adecuadas para investigar la web.

Las credenciales no deben escribirse aquí ni subirse a GitHub. Los secretos pertenecen al `.env` o al sistema de autenticación del perfil instalado.

Cada perfil tiene su propio `config.yaml`. Configurar `commerce-test` mediante `hermes -p commerce-test ...` no modifica `default`.

Además, cuando actualicemos la distribución, Hermes preservará por defecto los ajustes locales de `config.yaml`. Solo `--force-config` lo sustituiría de nuevo por el archivo publicado en este repositorio.

### `skills/market-intelligence/SKILL.md`

Es el procedimiento para realizar un Market Scan. Hermes descubre la skill por su cabecera YAML y la carga cuando la petición coincide con su descripción o cuando se la pedimos explícitamente.

La skill enseña al agente a:

1. leer el producto solicitado;
2. identificar clientes potenciales;
3. buscar competidores;
4. comparar precios;
5. interpretar señales de demanda sin presentarlas como ventas verificadas;
6. comparar Amazon, eBay, Google Shopping y Odoo;
7. asignar puntuaciones de oportunidad;
8. recomendar `LAUNCH`, `SMALL TEST`, `INVESTIGATE FURTHER` o `DO NOT LAUNCH`.

La skill no contiene integraciones con Amazon, eBay, Google u Odoo. Tampoco concede permisos para publicar o gastar.

### `knowledge/products/rtx-pro-6000-server.yaml`

Es nuestra primera ficha de producto estructurada. Separa:

- especificaciones conocidas del producto;
- mercados y clientes objetivo;
- escenarios de precio que son hipótesis de planificación;
- información que el agente no puede inventar;
- acciones que requieren aprobación humana.

`knowledge/` es una carpeta propia de esta distribución. Incluirla en `distribution_owned` hace que el archivo se instale, pero no inyecta automáticamente todo su contenido en cada conversación. La skill indica cuándo debe consultarse el YAML. Una de las primeras pruebas será confirmar que el agente lo localiza y lo lee correctamente dentro del perfil instalado.

### `.gitignore`

Evita versionar credenciales y datos locales como `.env`, `auth.json`, memorias, sesiones, logs y bases de datos de estado.

La exclusión de Git y la exclusión del instalador son protecciones distintas. Antes de cada commit hay que seguir comprobando que no se estén añadiendo secretos.

## Qué ocurre al instalar esta distribución

Al ejecutar la instalación desde GitHub, Hermes:

1. clona temporalmente el repositorio;
2. lee `distribution.yaml` y muestra el manifiesto;
3. comprueba que la versión instalada cumple `hermes_requires`;
4. crea el perfil con el nombre solicitado;
5. copia las rutas incluidas en `distribution_owned`;
6. elimina el repositorio Git temporal de la copia instalada;
7. mantiene credenciales, memorias y sesiones separadas del perfil `default`.

La distribución instalada no es un clon Git editable. GitHub es la fuente versionada; `hermes profile update` vuelve a obtenerla y aplica los cambios publicados.

## Estado real de la versión 0.1.0

| Parte | Estado |
| --- | --- |
| Identidad comercial | Preparada en `SOUL.md` |
| Ficha de la RTX PRO 6000 | Preparada en `knowledge/` |
| Procedimiento de Market Scan | Preparado en la skill |
| Instalación como perfil separado | Preparada mediante `distribution.yaml` |
| Modelo y proveedor | No fijados por la distribución |
| Credenciales | No incluidas, deliberadamente |
| Búsqueda web | No configurada por esta distribución |
| Amazon Seller, eBay, Google y Odoo | No conectados |
| Publicación, compras y gasto | Prohibidos en esta fase |
| Docker y sandbox | No configurados |
| MCP, gateway y cron | No configurados |

Por tanto, la versión actual es una base de investigación controlada. Tiene identidad, datos y método, pero todavía no tiene todas las capacidades externas necesarias para hacer un Market Scan autónomo completo.

## Instalación segura como `commerce-test`

Primero comprueba la versión:

```bash
hermes --version
```

Debe ser compatible con Hermes `>=0.14.0`.

Instala el repositorio sin sustituir `default`:

```bash
hermes profile install https://github.com/anamtb/hermes_agent.git --name commerce-test
```

No añadimos `--yes` en la primera instalación para poder revisar el manifiesto antes de confirmar.

Comprueba el resultado:

```bash
hermes profile list
hermes profile show commerce-test
hermes profile info commerce-test
hermes -p commerce-test skills list
```

## Configurar únicamente el perfil de prueba

Como `config.yaml` está vacío y las credenciales nunca se distribuyen, puede ser necesario configurar el modelo y la autenticación de `commerce-test` antes del primer chat.

La forma guiada recomendada por Hermes es:

```bash
hermes -p commerce-test setup --portal
```

También se puede seleccionar proveedor y modelo con:

```bash
hermes -p commerce-test model
```

Estos comandos actúan sobre `commerce-test` porque llevan `-p commerce-test`. No deben ejecutarse sin `-p` si queremos mantener intacta la configuración de `default`.

## Primera prueba funcional

Cuando el perfil tenga un modelo y una herramienta de búsqueda disponibles, podremos iniciar una sesión específica:

```bash
hermes -p commerce-test chat
```

Petición de prueba sugerida:

```text
Usa la skill market-intelligence. Lee el producto definido en
knowledge/products/rtx-pro-6000-server.yaml y prepara un Market Scan.
No publiques, no compres, no cambies precios y no gastes dinero.
Separa hechos verificados, señales, hipótesis e información desconocida.
```

La prueba debe confirmar, en este orden:

1. Hermes selecciona o carga `market-intelligence`.
2. La skill encuentra y lee el YAML del producto.
3. El agente reconoce qué datos faltan y no los inventa.
4. Solo investiga con las herramientas autorizadas disponibles.
5. Genera análisis por canal, ranking y recomendación.
6. No realiza ninguna acción comercial.

Si el perfil no puede buscar en Internet, no significa necesariamente que la skill esté mal: puede significar que falta configurar la herramienta correspondiente. Si no encuentra el YAML, entonces tendremos que corregir cómo la skill resuelve la ruta dentro del perfil.

## Actualizaciones posteriores

El ciclo de desarrollo será:

```text
editar el repositorio
        ↓
validar los cambios
        ↓
commit y push a GitHub
        ↓
hermes profile update commerce-test
        ↓
probar con -p commerce-test
```

Para instalar los cambios publicados sin perder la configuración local, memorias o sesiones:

```bash
hermes profile update commerce-test
```

Evita `--force-config` salvo que quieras reemplazar deliberadamente la configuración local de `commerce-test` por el `config.yaml` vacío de la distribución.

## Errores conceptuales frecuentes

- Subir el repositorio a GitHub no instala ni ejecuta el agente.
- Instalar el perfil no configura automáticamente credenciales privadas.
- Una skill aporta instrucciones; no crea por sí sola una API o herramienta.
- `knowledge/` aporta datos; no equivale a la memoria del agente.
- Un perfil separa el estado de Hermes, pero no es un sandbox de seguridad.
- `SOUL.md` establece conducta esperada, pero los permisos técnicos siguen siendo necesarios.
- `config.yaml: {}` no está roto: indica que todavía no imponemos configuración técnica desde la distribución.

## Documentación oficial

- [Introducción a Hermes Agent](https://hermes-agent.nousresearch.com/docs/)
- [Perfiles: varios agentes aislados](https://hermes-agent.nousresearch.com/docs/user-guide/profiles)
- [Distribuciones de perfiles](https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions)
- [Referencia de comandos de perfiles](https://hermes-agent.nousresearch.com/docs/reference/profile-commands/)
- [Configuración](https://hermes-agent.nousresearch.com/docs/user-guide/configuration/)
- [Sistema de skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/)
- [Qué función cumple cada archivo](https://hermes-agent.nousresearch.com/docs/user-guide/which-file-does-what)
