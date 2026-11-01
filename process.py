# -*- coding: utf-8 -*-
"""Limpia y calcula: filtra lo leído según config/productos.yml y calcula el precio por kilo.

Uso: python process.py raw/AAAA-MM-DD  -> escribe data/AAAA-MM-DD.json
El archivo de salida trae dos listas:
  rows        = productos que se quedan, con su $/kg
  descartados = lo que trajeron las búsquedas y se botó, con el motivo
"""
import json, re, sys
from collections import Counter
from pathlib import Path

import configuracion as cfg
from configuracion import sin_tildes

ROOT = cfg.ROOT


# ---------- peso ----------
def parse_kg(name, size=''):
    s = (name + ' ' + (size or '')).lower().replace(',', '.')
    m = re.search(r'(\d+)\s*(?:un|unid|unidades)\.?\s*de\s*(\d+)\s*g', s) or re.search(r'(\d+)\s*x\s*(\d+)\s*g', s)
    if m:
        return int(m.group(1)) * int(m.group(2)) / 1000
    m = re.search(r'(\d+(?:\.\d+)?)\s*kg', s)
    if m:
        return float(m.group(1))
    m = re.search(r'(\d+(?:\.\d+)?)\s*g(?:r|rs|ramos)?\b', s)
    if m:
        g = float(m.group(1))
        # "100 g 10 un." (Jumbo/Santa Isabel) => unidades de g c/u
        m2 = re.search(r'\d+\s*g(?:r)?\.?\s+(\d+)\s*un', s)
        if m2 and not re.search(r'1\s*kg', s):
            return g * int(m2.group(1)) / 1000
        return g / 1000
    return None


def lider_kg(name):
    s = name.lower().replace(',', ' ,')
    m = re.search(r'(\d+)\s*un\s*de\s*(\d+)\s*g', s)
    if m:
        return int(m.group(1)) * int(m.group(2)) / 1000
    return parse_kg(name.split(',')[-1])


def multibuy(promo):
    """'5 x $3.000' -> (5, 600)"""
    m = re.search(r'(\d+)\s*x\s*\$\s*([\d.]+)', promo or '')
    if m:
        q, t = int(m.group(1)), int(m.group(2).replace('.', ''))
        if q > 1:
            return q, round(t / q)
    return None


def url_completa(url, base):
    if not url or url.startswith('http'):
        return url
    return base.rstrip('/') + '/' + url.lstrip('/')


# ---------- filtro ----------
def clasificar(r, c, productos, excl_global):
    """Devuelve (producto, None) si se queda, o (None, motivo) si se descarta."""
    nom = sin_tildes(r['nombre'])
    p = next((p for p in productos if p['incluir'].search(nom)), None)
    if not p:
        return None, 'no calza con ningún producto (incluir)'
    if excl_global and (m := excl_global.search(nom)):
        return None, f'excluir_global: "{m.group(0)}"'
    if p['excluir'] and (m := p['excluir'].search(nom)):
        return None, f'{p["nombre"]}: excluir "{m.group(0)}"'
    if p['requiere'] and not p['requiere'].search(nom):
        return None, f'{p["nombre"]}: no tiene ninguna palabra de "requiere"'
    if p['solo_congelado'] and not es_congelado(r, c, p):
        return None, f'{p["nombre"]}: no es congelado'
    return p, None


def es_congelado(r, c, p):
    if re.search(r'congel|\bcong\b', r['nombre'], re.I) or re.search(r'-cong-|congel', r['url'] or '', re.I):
        return True
    if p['asumir_congelado']:
        return True
    return bool(c['congelado_re'] and c['congelado_re'].search(str(r['categoria_web'] or '')))


# ---------- cálculo ----------
def calcular(r, c, prod):
    price, lst, ppk = r['precio'], r['precio_normal'] or r['precio'], r['ppk']
    card, promo = r['precio_tarjeta'], r['promo']
    kg_name = lider_kg(r['nombre']) if c['clave'] == 'lider' else parse_kg(r['nombre'], r['formato'])
    kg = r['kg_unidad']
    if ppk and price:
        kg_from_ppk = price / ppk
        # se confía en el $/kg que publica la cadena salvo que sea implausible (error de catálogo)
        kg = kg_name if (kg_name and (kg_from_ppk > 3 or kg_from_ppk < 0.02)) else kg_from_ppk
    elif kg_name:
        kg = kg_name
    ppk_n = round(lst / kg) if (kg and lst) else None
    ppk_c = round(price / kg) if (kg and price) else None
    mb = multibuy(promo)
    ppk_mb = round(mb[1] / kg) if (mb and kg) else None
    ppk_card = round(card / kg) if (card and kg) else None
    best = min([x for x in (ppk_c, ppk_mb, ppk_card) if x] or [None]) if kg else None
    on_promo = bool((lst and price and price < lst) or mb or card)
    return dict(cadena=c['nombre'], cat=prod['nombre'], sku=r['nombre'].strip(),
                marca=(r['marca'] or '').strip().title().replace('Del', 'del'),
                kg=round(kg, 3) if kg else None, p_normal=lst, p_actual=price, p_tarjeta=card,
                ppk_normal=ppk_n, ppk_actual=ppk_c, ppk_promo_min=best if on_promo else None,
                promo=(promo or '').strip(), en_promo=on_promo, stock=bool(r['stock']),
                url=url_completa(r['url'], c['url_base']), busqueda=r['busqueda'])


def main():
    if len(sys.argv) < 2:
        sys.exit('Uso: python process.py raw/AAAA-MM-DD')
    D = Path(sys.argv[1])
    if not D.is_absolute() and not D.exists():
        D = ROOT / D
    fecha = D.name
    productos, excl_global = cfg.productos()
    cadenas = cfg.cadenas(solo_activas=False)

    rows, descartados, vistos = [], [], set()
    for clave, c in cadenas.items():
        f = D / f'{clave}.json'
        if not f.exists():
            continue
        for r in json.loads(f.read_text(encoding='utf-8')):
            k = (clave, r.get('url') or r['nombre'])
            if k in vistos:  # el mismo producto apareció en dos búsquedas
                continue
            vistos.add(k)
            prod, motivo = clasificar(r, c, productos, excl_global)
            if prod:
                rows.append(calcular(r, c, prod))
            else:
                descartados.append(dict(cadena=c['nombre'], sku=r['nombre'], busqueda=r['busqueda'],
                                        motivo=motivo, url=url_completa(r['url'], c['url_base'])))

    (ROOT / 'data').mkdir(exist_ok=True)
    out = ROOT / 'data' / f'{fecha}.json'
    out.write_text(json.dumps({'fecha': fecha, 'rows': rows, 'descartados': descartados},
                              ensure_ascii=False, indent=0), encoding='utf-8')
    print(f'{len(rows)} productos se quedan, {len(descartados)} descartados -> {out.relative_to(ROOT)}')
    print('Por cadena:', dict(Counter(r['cadena'] for r in rows)))
    print('Por producto:', dict(Counter(r['cat'] for r in rows)))
    sin_kg = [(r['cadena'], r['sku']) for r in rows if not r['kg']]
    if sin_kg:
        print(f'Sin peso identificable ({len(sin_kg)}, no entran al $/kg):', sin_kg)


if __name__ == '__main__':
    main()
