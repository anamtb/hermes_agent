# Amazon SP-API scaffold

Estado: **SCAFFOLDED / no operativo**.

Este MCP solo expone `amazon_get_capabilities`. No autentica, no hace HTTP, no
consulta catálogos y no publica listings. Las capacidades no implementadas se
declaran como `false`.

Variables reservadas para una integración futura (solo en `runtime/.env` o en
el entorno, nunca en Git):

```text
AMAZON_SP_API_CLIENT_ID
AMAZON_SP_API_CLIENT_SECRET
AMAZON_SP_API_REFRESH_TOKEN
AMAZON_SELLER_ID
AMAZON_MARKETPLACE_ID
```

El marketplace y seller no se deducirán ni se codificarán. La futura
integración deberá validar configuración, hacer preflight y exigir aprobación
antes de cualquier publicación.
