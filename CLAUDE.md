# Monitor de precios de supermercados (Pedro)

Lee cada semana precios de productos en supermercados chilenos, calcula el precio por kilo,
guarda historial y (desde la Etapa 4) sugiere dónde comprar. Corre en GitHub Actions (Ubuntu, Chromium sin ventana).
Viene de la base de Ann (vacuno congelado, Windows + Edge) y se adapta según el instructivo del proyecto,
por etapas: 1 nube y configuración · 2 productos y cadenas de Pedro · 3 automatización semanal ·
4 sugerido de dónde comprar · 5 página de precios en la app (app-pasteleria-matesic en Vercel).

## Cómo funciona
- `config/productos.yml`: qué se busca (busquedas), qué se queda (incluir, requiere), qué se bota (excluir, excluir_global),
  y si se exige congelado. Mayúsculas y tildes no importan; cada palabra es un pedazo de texto (o expresión regular).
- `config/cadenas.yml`: qué cadenas se leen, si están activas y cómo se leen (`pedir` o `navegar`).
- `scraper.py` + `extractores.js`: abre cada cadena en Chromium sin ventana y guarda TODO lo que trae cada búsqueda
  en `raw/<fecha>/<cadena>.json` (sin filtrar). `_resumen.json` dice qué cadena funcionó, falló o bloqueó.
  Jumbo, Santa Isabel, Unimarc y Tottus: forma `pedir` (fetch desde la propia página).
  Líder: forma `navegar` (bloquea fetch; se abre cada búsqueda y se lee __NEXT_DATA__).
- `process.py`: filtra según productos.yml y calcula $/kg → `data/<fecha>.json` con `rows` (se quedan) y
  `descartados` (con motivo). Si una cadena publica $/kg, se usa su peso salvo que sea implausible.
- `report.py`: Excel opcional en `reportes/` (no se sube al repositorio).
- `run.py`: corre los tres pasos con la fecha de Chile. `--solo jumbo,tottus`, `--sin-excel`.
- `.github/workflows/levantamiento.yml`: hoy solo manual (Run workflow); deja el resultado para descargar.

## Reglas
- Nunca resolver captchas ni evadir bloqueos anti-robot (no cambiar user agent para ocultar el navegador automático,
  no usar proxies). Si una cadena bloquea, se salta y se reporta.
- No inventar productos, cadenas, precios ni pesos. Producto sin peso identificable queda fuera del $/kg y del sugerido.
- No incluir datos de FT Foods (lista de precios, clientes).
- Si una cadena da 0 productos o cae >30% vs la semana anterior: revisar su lector en extractores.js antes de tocar process.py.
- Después de cada cambio, comparar al menos 3 precios contra el sitio y mostrar la comparación.
- Explicar a Pedro en español simple, sin tecnicismos; si se usa uno, definirlo. Esperar su aprobación entre etapas.
- Antes de agregar una cadena nueva, revisar si sus términos de uso permiten la lectura automática.

## Estado
- Etapa 1: código adaptado. El cálculo se validó contra la foto de Ann del 2026-10-02 (225 de 225 productos con
  el mismo peso, precios y $/kg). Lectura desde GitHub Actions: pendiente de la primera ejecución.

## Límites conocidos
- Búsqueda por palabra clave: puede faltar algún producto.
- Santa Isabel no expone en la búsqueda las promos "lleva X por $Y".
- Unimarc: algunas ofertas pueden ser precio Club Unimarc.
- Precios web de la ubicación por defecto del sitio; pueden diferir de la tienda.
