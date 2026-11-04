# -*- coding: utf-8 -*-
"""Lee config/productos.yml y config/cadenas.yml, y revisa que estén bien escritos."""
import re
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


def sin_tildes(s):
    s = unicodedata.normalize('NFD', (s or '').lower())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def _regex(palabras, donde):
    if not palabras:
        return None
    partes = []
    for p in palabras:
        p = sin_tildes(str(p))
        try:
            re.compile(p)
        except re.error as e:
            raise SystemExit(f'Error en {donde}: la palabra "{p}" no se entiende ({e}).')
        partes.append(f'(?:{p})')
    return re.compile('|'.join(partes))


def productos():
    d = yaml.safe_load((ROOT / 'config' / 'productos.yml').read_text(encoding='utf-8')) or {}
    lista = d.get('productos') or []
    if not lista:
        raise SystemExit('config/productos.yml no tiene productos.')
    excl_global = _regex(d.get('excluir_global'), 'excluir_global')
    vistos = set()
    out = []
    for p in lista:
        nombre = p.get('nombre')
        if not nombre or not p.get('busquedas') or not p.get('incluir'):
            raise SystemExit(f'config/productos.yml: cada producto necesita nombre, busquedas e incluir ({p}).')
        if nombre in vistos:
            raise SystemExit(f'config/productos.yml: el producto "{nombre}" está repetido.')
        vistos.add(nombre)
        unidad = str(p.get('unidad', 'kg')).lower()
        if unidad not in ('kg', 'l', 'un'):
            raise SystemExit(f'config/productos.yml: "{nombre}" tiene unidad "{unidad}"; debe ser kg, l o un.')
        out.append(dict(
            nombre=nombre,
            unidad=unidad,
            busquedas=[str(b) for b in p['busquedas']],
            incluir=_regex(p['incluir'], f'{nombre}.incluir'),
            excluir=_regex(p.get('excluir'), f'{nombre}.excluir'),
            requiere=_regex(p.get('requiere'), f'{nombre}.requiere'),
            marcas=_regex(p.get('marcas'), f'{nombre}.marcas'),
            excluir_marcas=_regex(p.get('excluir_marcas'), f'{nombre}.excluir_marcas'),
            referencia=str(p.get('referencia') or ''),
            solo_congelado=bool(p.get('solo_congelado')),
            asumir_congelado=bool(p.get('asumir_congelado')),
        ))
    return out, excl_global


def busquedas():
    """Todas las búsquedas, sin repetir, en el orden del archivo."""
    vistas = []
    for p in productos()[0]:
        for b in p['busquedas']:
            if b not in vistas:
                vistas.append(b)
    return vistas


def cadenas(solo_activas=True):
    d = yaml.safe_load((ROOT / 'config' / 'cadenas.yml').read_text(encoding='utf-8')) or {}
    out = {}
    for clave, c in (d.get('cadenas') or {}).items():
        for campo in ('nombre', 'forma', 'url_inicio', 'url_base'):
            if not c.get(campo):
                raise SystemExit(f'config/cadenas.yml: a la cadena "{clave}" le falta "{campo}".')
        if c['forma'] not in ('pedir', 'navegar'):
            raise SystemExit(f'config/cadenas.yml: "{clave}" tiene forma "{c["forma"]}"; debe ser pedir o navegar.')
        if solo_activas and not c.get('activa', True):
            continue
        c = dict(c)
        c['clave'] = clave
        c['max_paginas'] = int(c.get('max_paginas') or 1)
        c['congelado_re'] = re.compile(c['congelado_si_categoria'], re.I) if c.get('congelado_si_categoria') else None
        out[clave] = c
    return out
