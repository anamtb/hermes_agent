# Hermes Commerce Agent

La explicación visual completa de la arquitectura y del recorrido de un
producto está en [`docs/hermes-commerce-guide/`](docs/hermes-commerce-guide/README.md).

Distribución reutilizable de Hermes Agent para llevar productos desde la
investigación comercial hasta Odoo Ecommerce y Google Merchant con controles de
aprobación explícitos.

```text
Research → Pricing → Odoo → Google Merchant → Review
```

El alcance actual es Odoo y Google Merchant. Amazon y eBay quedan como posibles
canales de investigación, no como integraciones de publicación.

## Qué puede pedir el usuario

El usuario puede hablar en términos de negocio:

```text
Quiero comercializar el producto X. Tengo un coste de 640 €, 20 unidades
y este proveedor. Analiza el mercado, proponme precio, prepáralo en Odoo
y después publícalo en Google Merchant.
```

Hermes se ocupa de identificar el producto, separar hechos de estimaciones,
investigar el mercado, calcular escenarios, descubrir las opciones técnicas y
preparar las operaciones. No obliga al usuario a conocer IDs internos si puede
descubrirlos con las herramientas.

El usuario conserva tres decisiones obligatorias:

1. aprobar el precio;
2. aprobar la publicación en Odoo;
3. aprobar la publicación en Google Merchant.

## Flujo de producto

La skill principal vive en
`skills/commerce-product-launch/SKILL.md` y usa estos estados:

```text
DISCOVERY
→ PRODUCT_IDENTITY
→ SUPPLIER_AND_COST
→ MARKET_RESEARCH
→ PRICING_PROPOSAL
→ PRICE_APPROVAL
→ ODOO_DRAFT
→ IMAGE_SELECTION
→ ODOO_VALIDATION
→ ODOO_PUBLISH_APPROVAL
→ ODOO_PUBLISHED
→ MERCHANT_PREFLIGHT
→ MERCHANT_PUBLISH_APPROVAL
→ MERCHANT_SUBMITTED
→ MERCHANT_REVIEW
```

Investigación y lectura no requieren aprobación. Precio y las dos publicaciones
sí. La aprobación de una fase nunca autoriza automáticamente la siguiente.

## Fuentes de verdad

Cada tipo de información tiene un propietario claro:

| Información | Fuente de verdad |
| --- | --- |
| Identidad, especificaciones y fuentes verificables | Dossier en `knowledge/products/` |
| Catálogo, coste, proveedores, stock y publicación | Odoo |
| Precio, moneda y disponibilidad que ve el cliente | Landing pública de Odoo/JSON-LD |
| Estado e incidencias del canal | Google Merchant |
| Investigación competitiva fechada | Dossier + fuentes externas |

No se calcula el IVA a ciegas para publicar en Merchant. El preflight compara el
payload con el precio, moneda y disponibilidad observados en la landing.

## Un YAML por producto

`knowledge/products/rtx-pro-6000-server.yaml` se conserva como primer dossier.
No es código especial para una sola RTX y no debe borrarse al añadir productos.

Cuando el usuario presenta un producto nuevo, Hermes:

1. establece fabricante, modelo y variante exactos;
2. recopila datos verificables y marca lo desconocido;
3. crea o actualiza un YAML con un slug estable, por ejemplo
   `fabricante-modelo.yaml`;
4. guarda fuentes, fechas, estimaciones y decisiones;
5. enlaza el dossier con Odoo cuando exista el producto operativo.

La plantilla reusable es `knowledge/products/_template.yaml`. Los dossiers no
deben contener secretos ni copiar stock/precio cambiante como si fueran datos
operativos actuales. Para esos valores siempre se vuelve a consultar Odoo.

## Identificador maestro

Se prefiere un SKU/MPN estable:

```text
Odoo default_code
    ↓
Google Merchant offerId
    ↓
futuros seller SKU de otros canales
```

Los IDs internos de Odoo sirven para llamadas técnicas, no como identidad
cross-channel cuando existe un SKU/MPN adecuado. Nunca se inventa un GTIN.

## Pricing reusable

`mcp/commerce/pricing.py` implementa un cálculo puro y testeable. La herramienta
`commerce_calculate_pricing` devuelve:

- price floor;
- escenario conservador / venta rápida;
- escenario moderado / equilibrado;
- escenario agresivo / margen alto;
- precio neto, impuesto, precio final, costes, comisiones, beneficio y margen;
- costes ausentes y carácter provisional del cálculo.

Los precios de mercado se interpretan como precios finales para cliente. La
comisión porcentual se aplica al precio neto. Si faltan costes opcionales se
tratan provisionalmente como cero, pero se señalan de forma explícita: Hermes no
puede presentar ese floor como completo. Ningún escenario baja del floor salvo
que el usuario autorice expresamente una liquidación con pérdida.

## MCP de Odoo

`mcp/odoo/odoo_mcp.py` mantiene las herramientas existentes y añade/fortalece:

- `odoo_get_commerce_product`: ficha, variantes, coste, GTIN/barcode, impuestos,
  stock, compañía, almacenes, proveedores y verificación de landing/imagen;
- `odoo_list_product_suppliers`: proveedores y referencias/precios configurados,
  solo lectura;
- `odoo_search_suppliers`: descubre proveedores existentes con nombres humanos;
- `odoo_set_product_cost`: registra coste en un borrador con aprobación;
- `odoo_set_product_supplier`: asocia un proveedor existente con aprobación,
  pero nunca crea un contacto nuevo;
- `odoo_publish_product`: requiere tanto habilitación local como
  `confirmation="PUBLICAR_EN_ODOO"`;
- gestión de imágenes desde archivo o URL aprobada con protección frente a
  hosts privados.

Odoo es el catálogo operativo. Si un campo o permiso no está disponible, Hermes
debe informarlo como `unknown/unavailable`, no inventarlo.

## MCP de Google Merchant

`mcp/google-merchant/google_merchant_mcp.py` ofrece:

- listado de cuentas, fuentes y productos;
- `google_merchant_preflight_product`, que normaliza el payload, comprueba URLs
  públicas y contrasta precio/moneda/disponibilidad con la landing sin publicar;
- `google_merchant_upsert_product`, protegido por
  `confirmation="PUBLICAR_EN_GOOGLE_MERCHANT"` y por el mismo preflight;
- `google_merchant_get_product` y `google_merchant_get_product_issues` para
  revisar el resultado procesado.

Cuenta, fuente, idioma, feed label, moneda, dominio y offer ID no se codifican
para una instalación concreta. Se leen de configuración local, herramientas de
descubrimiento o parámetros verificados.

Una inserción aceptada no implica aprobación: Merchant procesa el producto de
forma asíncrona y puede dejarlo pendiente o rechazado con incidencias.

## Política de imágenes

Hermes pregunta siempre si se usará:

1. una imagen proporcionada por el usuario; o
2. una imagen localizada en Internet.

Para Internet debe coincidir la variante exacta, priorizar fabricante o
distribuidor autorizado, mostrar la fuente original y pedir aprobación. No usa
thumbnails de búsqueda ni accede a localhost, redes privadas o link-local.

## Requisitos

- Hermes Agent `>=0.14.0`;
- Python compatible con los requisitos de cada MCP;
- una instancia Odoo con JSON-2 API y permisos mínimos necesarios;
- una cuenta Google Merchant con fuente de datos API;
- OAuth de escritorio de Google con scope de Merchant;
- herramienta de búsqueda web para investigación de mercado.

Instala todas las dependencias compartidas:

```bash
python3 -m pip install -r requirements.txt
```

También se mantienen requisitos por MCP para despliegues selectivos:

```bash
python -m pip install -r mcp/odoo/requirements.txt
python -m pip install -r mcp/google-merchant/requirements.txt
python -m pip install -r mcp/commerce/requirements.txt
```

## Configuración y secretos

Los secretos pertenecen exclusivamente al `.env` del perfil o al entorno de
ejecución. Nunca a Git, `config.yaml`, un dossier o un prompt compartido.

Variables usadas:

```text
ODOO_BASE_URL
ODOO_API_KEY
ODOO_ALLOW_PUBLISH
HERMES_PRODUCT_IMAGE_DIR          # opcional
GOOGLE_OAUTH_CLIENT_ID
GOOGLE_OAUTH_CLIENT_SECRET
GOOGLE_OAUTH_REFRESH_TOKEN
GOOGLE_MERCHANT_ACCOUNT_ID
```

`config.yaml` declara únicamente los tres servidores MCP mediante rutas
portables basadas en `${HERMES_HOME}`; no fija modelo, proveedor ni secretos.
`mcp.json` contiene la misma topología para el formato de distribución. En las
versiones actuales de Hermes, el runtime toma `mcp_servers` de `config.yaml`.
El comando predeterminado es `python3`, apropiado para el despliegue Linux; una
instalación Windows puede cambiarlo localmente por su intérprete Python.

En una instalación nueva, esos servidores quedan declarados por la
distribución. En un perfil existente, `hermes profile update` preserva
`config.yaml`; añade o actualiza los servidores con `hermes mcp add` y recárgalos
sin usar `--force-config` si quieres conservar tus ajustes locales.

El flujo local usado para generar OAuth es una utilidad de instalación y no se
versiona. No compartas el archivo de credenciales ni ejecutes `Get-Content` sobre
él en conversaciones o logs.

## Instalación y actualización del perfil

Instalación inicial:

```bash
hermes profile install https://github.com/anamtb/hermes_agent.git --name commerce-test
hermes -p commerce-test setup --portal
```

Actualización sin reemplazar la configuración local:

```bash
hermes profile update commerce-test
```

Evita `--force-config` salvo que quieras sustituir deliberadamente la
configuración local del perfil.

## Validación de desarrollo

```bash
python -m py_compile mcp/commerce/pricing.py
python -m py_compile mcp/commerce/commerce_mcp.py
python -m py_compile mcp/odoo/odoo_mcp.py
python -m py_compile mcp/google-merchant/product_validation.py
python -m py_compile mcp/google-merchant/google_merchant_mcp.py
python -m unittest discover -s tests -v
```

Las pruebas unitarias no llaman a Odoo ni a Google y no publican nada.

## Primera prueba segura

```bash
hermes -p commerce-test chat
```

Prompt sugerido:

```text
Quiero comercializar un producto nuevo. Usa commerce-product-launch.
Empieza por identificarlo y preparar el dossier. Haz research y pricing,
pero no crees nada en Odoo ni publiques hasta que apruebe cada gate.
```

La prueba debe mostrar el estado del flujo, separar hechos/datos aportados/
estimaciones/desconocidos y detenerse en `PRICE_APPROVAL`.
