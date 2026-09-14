# Guía visual de Hermes Commerce Agent

Esta carpeta explica cómo está construido el agente, qué sistema es responsable
de cada dato y qué sucede cuando una persona pide publicar un producto nuevo.

## Recorrido recomendado

1. [Arquitectura del agente](01-arquitectura.md): piezas que forman Hermes y
   cómo se conectan.
2. [Ciclo de vida de un producto](02-ciclo-de-producto.md): recorrido completo
   y puntos donde el agente debe detenerse.
3. [Ejemplo de conversación](03-ejemplo-publicacion.md): ejemplo práctico desde
   la petición inicial hasta la revisión en Google Merchant.
4. [Fuentes de verdad y seguridad](04-fuentes-y-seguridad.md): propietario de
   cada dato, archivos persistentes y operaciones protegidas.

## Diagramas Mermaid originales

Los archivos fuente se encuentran en [`diagrams/`](diagrams/README.md):

- [`arquitectura.mmd`](diagrams/arquitectura.mmd)
- [`ciclo-producto.mmd`](diagrams/ciclo-producto.mmd)
- [`ejemplo-publicacion.mmd`](diagrams/ejemplo-publicacion.mmd)
- [`fuentes-de-verdad.mmd`](diagrams/fuentes-de-verdad.mmd)

GitHub renderiza automáticamente los bloques Mermaid incluidos en los
documentos Markdown. Los archivos `.mmd` también pueden copiarse en Mermaid
Live Editor o en otro visor compatible.

## Idea principal

Hermes no es una tienda ni una base de datos paralela. Es el coordinador del
proceso:

```text
Conversación con el usuario
→ expediente YAML del producto
→ investigación y propuesta de precio
→ borrador y publicación controlada en Odoo
→ comprobación de la página pública
→ envío controlado a Google Merchant
→ seguimiento de incidencias
```

Ningún producto se publica únicamente porque el usuario lo mencione. Primero se
confirma su identidad y después se atraviesan tres aprobaciones independientes:
precio, Odoo y Google Merchant.
