# PcComponentes / Mirakl scaffold

Estado: **SCAFFOLDED / no operativo**.

Este MCP solo expone `pccomponentes_get_capabilities`. No autentica, no hace
HTTP y no lee ni escribe productos, ofertas, precios, stock u órdenes. No se
asume ninguna URL privada ni contrato concreto de la API Mirakl.

Variables reservadas para una integración futura (solo en `runtime/.env` o en
el entorno, nunca en Git):

```text
PCCOMPONENTES_MIRAKL_API_URL
PCCOMPONENTES_MIRAKL_API_KEY
PCCOMPONENTES_SHOP_ID
```

La futura implementación deberá verificar la documentación y el contrato de
PcComponentes, hacer preflight y exigir aprobación antes de cualquier write.
