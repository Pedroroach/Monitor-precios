# -*- coding: utf-8 -*-
"""Muestra unos productos por cadena (para comparar precios contra los sitios). Uso: python muestra.py [fecha]"""
import glob, json, os, sys
from collections import defaultdict
ROOT = os.path.dirname(os.path.abspath(__file__))
f = os.path.join(ROOT, 'data', sys.argv[1] + '.json') if len(sys.argv) > 1 else max(glob.glob(os.path.join(ROOT, 'data', '20*.json')))
d = json.load(open(f, encoding='utf-8'))
por = defaultdict(list)
for r in d['rows']:
    por[r['cadena']].append(r)
print(f'Muestra de {os.path.basename(f)}')
for cad, rows in por.items():
    for r in rows[:4]:
        print(f"{cad} | {r['sku']} | hoy ${r['p_actual']} | normal ${r['p_normal']} | {r['kg']} kg | ${r['ppk_actual']}/kg | {r['url']}")
