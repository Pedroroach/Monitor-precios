# Monitor de precios

Lee precios de productos en supermercados de Chile (Jumbo, Santa Isabel, Unimarc, Tottus y Líder),
calcula el precio por kilo y guarda el historial. Corre solo en GitHub Actions.

## Qué se cotiza
- Productos: `config/productos.yml`
- Supermercados: `config/cadenas.yml`

Para cambiar algo, pídeselo a Claude Code en palabras simples, por ejemplo:
"Agrega el producto X. Búscalo como Y. Descarta Z." · "Apaga la cadena X." · "La ejecución del lunes falló, revisa por qué."

## Ejecutar a mano
En GitHub: pestaña **Actions** → **Levantamiento de precios** → **Run workflow**.
Al terminar, el resultado se descarga desde la misma ejecución (sección *Artifacts*).

## En un PC (opcional)
```
pip install -r requirements.txt
python -m playwright install chromium
python run.py              # todas las cadenas
python run.py --solo jumbo # una sola
```

## Qué deja cada ejecución
- `raw/<fecha>/` todo lo que trajo cada búsqueda, sin filtrar
- `data/<fecha>.json` productos que se quedan con su $/kg, y los descartados con el motivo
- `logs/<fecha>.log` qué pasó con cada cadena
