# 1. Arquitectura del agente

## Diagrama

```mermaid
flowchart LR
    U[Usuario] --> H[Hermes Commerce Agent]

    subgraph Cerebro_del_agente[Comportamiento y proceso]
        S[SOUL.md<br/>Reglas y límites]
        W[commerce-product-launch<br/>Flujo de trabajo]
        Y[knowledge/products<br/>Un dossier YAML por producto]
    end

    H --> S
    H --> W
    W <--> Y

    subgraph Herramientas_MCP[Herramientas especializadas]
        P[Commerce Pricing<br/>Precios, costes y márgenes]
        O[Odoo MCP<br/>Catálogo, stock, coste e imagen]
        G[Google Merchant MCP<br/>Preflight, envío y estado]
    end

    W --> P
    W --> O
    W --> G

    O <--> OD[(Odoo)]
    O --> LP[Página pública de Odoo]
    LP --> G
    G <--> GM[(Google Merchant Center)]

    CFG[config.yaml y mcp.json<br/>Conexiones portables] --> P
    CFG --> O
    CFG --> G
    ENV[.env local<br/>Credenciales e IDs privados] --> O
    ENV --> G
```

Fuente Mermaid: [`diagrams/arquitectura.mmd`](diagrams/arquitectura.mmd).

## Qué hace cada parte

### Usuario

Habla en términos comerciales. No necesita conocer el identificador interno de
una fuente de Google ni la estructura técnica de Odoo. Puede decir, por ejemplo:

```text
Quiero vender este producto. Tengo un coste de 640 €, veinte unidades y este
proveedor. Investiga el mercado y prepáralo para publicarlo.
```

### Hermes Commerce Agent

Interpreta la petición, determina el estado actual del proceso y decide qué
información o herramienta necesita. Coordina las piezas, pero no sustituye a
Odoo ni a Google Merchant.

### `SOUL.md`

Define las reglas permanentes del agente: no inventar costes, stock, GTIN,
proveedores, especificaciones ni derechos de imagen; distinguir hechos de
estimaciones; y pedir aprobación antes de acciones comerciales sensibles.

### Skill `commerce-product-launch`

Es el procedimiento operativo. Indica el orden de las fases, qué validaciones
deben ejecutarse y dónde se encuentran las tres puertas de aprobación.

### Dossiers YAML

Cada producto identificado tiene un archivo en `knowledge/products/`. Este
archivo conserva identidad, fuentes, investigación, estimaciones y decisiones.
Si el producto vuelve a aparecer en otra conversación, se actualiza el mismo
dossier en lugar de empezar desde cero.

El YAML no sustituye a Odoo para valores que cambian continuamente. El stock y
el precio publicado se vuelven a consultar en Odoo cuando se necesitan.

### MCP de pricing

Realiza cálculos deterministas: suelo de precio, impuestos, costes, beneficio,
margen y escenarios conservador, moderado y agresivo. No publica productos.

### MCP de Odoo

Es la interfaz con el catálogo operativo. Lee productos, variantes, stock,
proveedores, coste, impuestos y página pública. Las escrituras sensibles están
protegidas mediante confirmaciones explícitas.

### MCP de Google Merchant

Descubre cuentas y fuentes de datos, valida el producto contra la página pública,
lo envía solamente después de la autorización y consulta después su estado e
incidencias.

### Configuración y secretos

`config.yaml`, `mcp.json` y `distribution.yaml` hacen que el agente sea
instalable en distintos equipos. Los dominios, IDs de cuenta y credenciales
pertenecen al `.env` local de cada instalación y nunca a los dossiers o al
repositorio.
