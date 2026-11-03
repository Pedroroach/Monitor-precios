# -*- coding: utf-8 -*-
"""Lista, producto por producto, lo que se quedó y lo que se descartó (con el motivo).
Sirve para revisar los filtros de config/productos.yml.  Uso: python revisar.py [fecha]"""
import glob, json, os, sys
from collections import defaultdict
import configuracion as cfg

ROOT = str(cfg.ROOT)
f = os.path.join(ROOT, 'data', sys.argv[1] + '.json') if len(sys.argv) > 1 else max(glob.glob(os.path.join(ROOT, 'data', '20*.json')))
d = json.load(open(f, encoding='utf-8'))
productos = cfg.productos()[0]
quedan = defaultdict(list)
for r in d['rows']:
    quedan[r['cat']].append(r)
desc = defaultdict(list)
for r in d['descartados']:
    desc[r['busqueda']].append(r)

print(f'Revisión de {os.path.basename(f)}')
for p in productos:
    R = sorted(quedan[p['nombre']], key=lambda r: (r['cadena'], r['pu_actual'] or 10**9))
    print(f"\nPRODUCTO {p['nombre']} (por {p['unidad']}) — se quedan {len(R)}")
    for r in R:
        marca = ' [cantidad dudosa]' if r['cantidad_dudosa'] else ''
        print(f"  OK  | {r['cadena']} | {r['sku']} | ${r['p_actual']} | {r['cantidad']} {r['unidad']} | ${r['pu_actual']}/{r['unidad']}{marca}")
    for q in p['busquedas']:
        D = desc.pop(q, [])
        print(f"  búsqueda '{q}': {len(D)} descartados")
        for r in D:
            print(f"  NO  | {r['cadena']} | {r['sku']} | {r['motivo']}")
