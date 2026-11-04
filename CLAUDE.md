# Monitor de precios de supermercados (Pedro)

Lee cada semana precios de productos en supermercados chilenos, calcula el precio por kilo,
guarda historial y (desde la Etapa 4) sugiere dónde comprar. Corre en GitHub Actions (Ubuntu, Chromium sin ventana).
Viene de la base de Ann (vacuno congelado, Windows + Edge) y se adapta según el instructivo del proyecto,
por etapas: 1 nube y configuración · 2 productos y cadenas de Pedro · 3 automatización semanal ·
4 sugerido de dónde comprar · 5 página de precios en la app (app-pasteleria-matesic en Vercel).

## Cómo funciona
- `config/productos.yml`: insumos de la pastelería de la mamá de Pedro. Por producto: unidad de comparación (kg, l o un),
  qué se busca (busquedas), qué se queda (incluir, requiere, marcas), qué se bota (excluir, excluir_marcas, excluir_global),
  si se exige congelado y `referencia` (lo que paga hoy y dónde, para la Etapa 4). Marcas se comparan contra marca + nombre.
  Si varios productos calzan con un nombre, se prueba primero el de la búsqueda que lo trajo. Mayúsculas y tildes no importan; cada palabra es un pedazo de texto (o expresión regular).
- `config/cadenas.yml`: qué cadenas se leen, si están activas y cómo se leen (`pedir` o `navegar`).
- `scraper.py` + `extractores.js`: abre cada cadena en Chromium sin ventana y guarda TODO lo que trae cada búsqueda
  en `raw/<fecha>/<cadena>.json` (sin filtrar). `_resumen.json` dice qué cadena funcionó, falló o bloqueó.
  Jumbo, Santa Isabel, Unimarc y Tottus: forma `pedir` (fetch desde la propia página).
  Líder: forma `navegar` (bloquea fetch; se abre cada búsqueda y se lee __NEXT_DATA__).
- `process.py`: filtra según productos.yml y calcula el precio por unidad de medida (`pu_*`, con `cantidad` y `unidad`)
  → `data/<fecha>.json` con `rows` (se quedan) y `descartados` (con motivo). Kg y litros: si la cadena publica precio por
  esa unidad se usa su cantidad, salvo envase fuera de rango; si difiere >20% del nombre queda `cantidad_dudosa`.
  Por unidad (huevos): siempre del nombre, porque las cadenas publican "por unidad" = por envase.
- `revisar.py`: lista por producto lo que se quedó y lo descartado (corre en el workflow, se lee en el log).
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
  el mismo peso, precios y $/kg). Primera lectura desde GitHub Actions (2026-11-02): Jumbo, Santa Isabel y Unimarc OK
  (9 de 9 precios iguales a la ficha del producto); Tottus responde 403 y Líder pide "Robot or human?" → bloqueadas
  desde servidores. Santa Isabel cambió su sitio a Next.js (igual a Jumbo); su lector soporta ambos formatos.
- `verificar.py` abre la ficha de 3 productos por cadena y compara su precio con el levantamiento (corre en el workflow).
- Desde esta sesión en la nube de Claude no se puede entrar a los sitios ni descargar los artifacts de Actions:
  las pruebas se leen desde el log de la ejecución (gh api .../actions/jobs/<id>/logs).

- Etapa 2 (en curso): 18 productos según las respuestas de la mamá de Pedro (2026-11-03): marcas que usa, Máxima fuera
  en azúcar, mantequilla con sal Colun/Quillayes, crema Soprole normal, leche condensada Nestlé, cacao Gourmet,
  queso crema Green Bay/Philadelphia/Cuisine & Co, huevos extra; nuevos: limón sutil, galletas de vino Dos en Uno,
  frambuesa, maracuyá y lúcuma congeladas. Fuera: manjar y harina con polvos. Pendiente confirmar si usa azúcar flor,
  leche entera, chocolate de cobertura, polvos de hornear y esencia de vainilla (no los mencionó).
  Ella compra varias cosas en Alvi (mayorista, no está en el monitor) y fruta congelada fuera de supermercados. Cadenas: Jumbo, Santa Isabel,
  Unimarc. Tottus y Líder apagadas (bloquean desde GitHub), se decide en la Etapa 3.

## Límites conocidos
- Búsqueda por palabra clave: puede faltar algún producto.
- Santa Isabel no expone en la búsqueda las promos "lleva X por $Y".
- Unimarc: algunas ofertas pueden ser precio Club Unimarc.
- Precios web de la ubicación por defecto del sitio; pueden diferir de la tienda.
