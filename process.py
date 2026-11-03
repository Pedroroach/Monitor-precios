# -*- coding: utf-8 -*-
"""Limpia y calcula: filtra lo leído según config/productos.yml y calcula el precio por unidad de medida
(por kilo, por litro o por unidad, según el producto).

Uso: python process.py raw/AAAA-MM-DD  -> escribe data/AAAA-MM-DD.json
El archivo de salida trae dos listas:
  rows        = productos que se quedan, con su precio por unidad de medida (pu_*)
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


def parse_l(name, size=''):
    """Litros en el nombre o formato: '1 L', '1 lt', '200 ml', '500 cc', '6 x 1 L'."""
    s = (name + ' ' + (size or '')).lower().replace(',', '.')
    m = re.search(r'(\d+)\s*x\s*(\d+(?:\.\d+)?)\s*(l|lt|lts|litros?|ml|cc)\b', s)
    if m:
        v = float(m.group(2)) / (1000 if m.group(3) in ('ml', 'cc') else 1)
        return int(m.group(1)) * v
    m = re.search(r'(\d+(?:\.\d+)?)\s*(ml|cc)\b', s)
    if m:
        return float(m.group(1)) / 1000
    m = re.search(r'(\d+(?:\.\d+)?)\s*(l|lt|lts|litros?)\b', s)
    if m:
        return float(m.group(1))
    return None


def parse_un(name, size=''):
    """Unidades: '12 un', '30 unidades', '12 huevos', 'docena', 'bandeja 30'."""
    s = (name + ' ' + (size or '')).lower()
    if re.search(r'media docena', s):
        return 6
    if re.search(r'\bdocena', s):
        return 12
    m = re.search(r'(\d+)\s*(?:un\b|unid|unidades|huevos)', s) or re.search(r'bandeja\s*(?:de\s*)?(\d+)', s)
    if m:
        return int(m.group(1))
    return None


# precio por unidad que publica la cadena: cómo lo escribe cada una -> kg, l o un
UNIDADES_CADENA = {'kg': 'kg', 'kilo': 'kg', 'l': 'l', 'lt': 'l', 'lts': 'l', 'litro': 'l', 'litros': 'l',
                   'un': 'un', 'unidad': 'un', 'unidades': 'un'}
# rango creíble de envase, para desconfiar de un precio por unidad mal cargado en el catálogo
RANGO = {'kg': (0.005, 30), 'l': (0.005, 20), 'un': (1, 360)}


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
def filtro(r, c, p, nom):
    """None si el producto p acepta la fila, o el motivo si no."""
    if p['excluir'] and (m := p['excluir'].search(nom)):
        return f'{p["nombre"]}: excluir "{m.group(0)}"'
    if p['requiere'] and not p['requiere'].search(nom):
        return f'{p["nombre"]}: no tiene ninguna palabra de "requiere"'
    if p['solo_congelado'] and not es_congelado(r, c, p):
        return f'{p["nombre"]}: no es congelado'
    return None


def clasificar(r, c, productos, excl_global):
    """Devuelve (producto, None) si se queda, o (None, motivo) si se descarta.
    Si varios productos calzan con el nombre (ej. dos harinas), se prueba primero el de la búsqueda que lo trajo."""
    nom = sin_tildes(r['nombre'])
    if excl_global and (m := excl_global.search(nom)):
        return None, f'excluir_global: "{m.group(0)}"'
    cand = [p for p in productos if p['incluir'].search(nom)]
    if not cand:
        return None, 'no calza con ningún producto (incluir)'
    cand.sort(key=lambda p: r['busqueda'] not in p['busquedas'])
    motivos = []
    for p in cand:
        motivo = filtro(r, c, p, nom)
        if motivo is None:
            return p, None
        motivos.append(motivo)
    return None, ' / '.join(motivos)


def es_congelado(r, c, p):
    if re.search(r'congel|\bcong\b', r['nombre'], re.I) or re.search(r'-cong-|congel', r['url'] or '', re.I):
        return True
    if p['asumir_congelado']:
        return True
    return bool(c['congelado_re'] and c['congelado_re'].search(str(r['categoria_web'] or '')))


# ---------- cálculo ----------
def cantidad(r, c, unidad):
    """Cantidad del envase en la unidad del producto (kg, l o un) y si es dudosa.
    Se usa el precio por unidad que publica la cadena, salvo que dé un envase fuera de rango;
    si no publica, se lee del nombre. Si ambos existen y difieren más de 20%, queda marcado como dudoso."""
    nombre, formato, price = r['nombre'], r['formato'], r['precio']
    if unidad == 'kg':
        q_nombre = lider_kg(nombre) if c['clave'] == 'lider' else parse_kg(nombre, formato)
        ppu = r['ppk']
        hint = r['kg_unidad']
    else:
        q_nombre = parse_l(nombre, formato) if unidad == 'l' else parse_un(nombre, formato)
        ppu = r.get('ppu') if UNIDADES_CADENA.get(str(r.get('ppu_unidad') or '').lower()) == unidad else None
        hint = None
    q = None
    if ppu and price:
        q_cadena = price / ppu
        lo, hi = RANGO[unidad]
        q = q_cadena if lo <= q_cadena <= hi else q_nombre
    if q is None:
        q = q_nombre or hint
    if unidad == 'un' and q:
        q = round(q)
    dudoso = bool(q and q_nombre and abs(q / q_nombre - 1) > 0.2)
    return q, dudoso


def calcular(r, c, prod):
    unidad = prod['unidad']
    price, lst = r['precio'], r['precio_normal'] or r['precio']
    card, promo = r['precio_tarjeta'], r['promo']
    q, dudoso = cantidad(r, c, unidad)
    pu_n = round(lst / q) if (q and lst) else None
    pu_c = round(price / q) if (q and price) else None
    mb = multibuy(promo)
    pu_mb = round(mb[1] / q) if (mb and q) else None
    pu_card = round(card / q) if (card and q) else None
    best = min([x for x in (pu_c, pu_mb, pu_card) if x] or [None]) if q else None
    on_promo = bool((lst and price and price < lst) or mb or card)
    return dict(cadena=c['nombre'], cat=prod['nombre'], unidad=unidad, sku=r['nombre'].strip(),
                marca=(r['marca'] or '').strip().title().replace('Del', 'del'),
                cantidad=round(q, 3) if q else None, cantidad_dudosa=dudoso, p_normal=lst, p_actual=price, p_tarjeta=card,
                pu_normal=pu_n, pu_actual=pu_c, pu_promo_min=best if on_promo else None,
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
    sin_q = [(r['cadena'], r['sku']) for r in rows if not r['cantidad']]
    if sin_q:
        print(f'Sin cantidad identificable ({len(sin_q)}, no entran al precio por unidad):', sin_q)
    dud = [(r['cadena'], r['sku'], r['cantidad']) for r in rows if r['cantidad_dudosa']]
    if dud:
        print(f'Cantidad dudosa ({len(dud)}, la cadena y el nombre no coinciden):', dud)


if __name__ == '__main__':
    main()
