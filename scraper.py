# -*- coding: utf-8 -*-
"""Lee los precios de cada cadena con un navegador Chromium sin ventana (Playwright).

Uso:  python scraper.py                    -> guarda raw/<hoy>/<cadena>.json
      python scraper.py --solo jumbo,tottus
      python scraper.py --ver               -> con ventana (para mirar qué pasa, solo en un PC)

Qué buscar y en qué cadenas está en config/. Guarda TODO lo que trae cada búsqueda;
el filtro lo hace process.py.
No resuelve captchas: si una cadena pide verificación anti-robot, se salta y queda en el log.
"""
import argparse, datetime as dt, json, sys, time, traceback
from urllib.parse import quote
from playwright.sync_api import sync_playwright

import configuracion as cfg

ROOT = cfg.ROOT
JS = (ROOT / 'extractores.js').read_text(encoding='utf-8')
BLOQUEO = ('robot or human', 'are you a robot', 'captcha', 'access denied', 'attention required', 'just a moment')


class Bloqueado(Exception):
    pass


def log(msg, fh):
    linea = f"{dt.datetime.now():%H:%M:%S} {msg}"
    print(linea, flush=True)
    fh.write(linea + '\n')


def revisar_bloqueo(page, nombre):
    t = (page.title() or '').lower()
    if any(b in t for b in BLOQUEO):
        raise Bloqueado(f'{nombre}: el sitio pidió verificación anti-robot ("{page.title()}"). No se resuelve; se salta.')


def abrir(page, url, nombre, espera):
    resp = page.goto(url, wait_until='domcontentloaded', timeout=60000)
    page.wait_for_timeout(espera)
    revisar_bloqueo(page, nombre)
    if resp is not None and resp.status in (401, 403, 429):
        raise Bloqueado(f'{nombre}: el sitio respondió {resp.status} (acceso denegado). Se salta.')


def leer_pidiendo(page, c, qs, fh):
    abrir(page, c['url_inicio'], c['clave'], 2500)
    page.evaluate(JS)  # evaluate evita bloqueos CSP de scripts inline
    res = page.evaluate('([c, qs, n]) => MV.leer(c, qs, n)', [c['clave'], qs, c['max_paginas']])
    for e in res['errores']:
        log(f'  {c["clave"]} búsqueda con error -> {e}', fh)
    if res['errores'] and len(res['errores']) == len(qs):
        raise RuntimeError(f'{c["clave"]}: fallaron todas las búsquedas.')
    return res['filas']


def leer_navegando(page, c, qs, fh):
    filas = []
    for q in qs:
        vistos = 0
        for pg in range(1, c['max_paginas'] + 1):
            u = c['url_busqueda'].format(q=quote(q)) + (f'&page={pg}' if pg > 1 else '')
            abrir(page, u, c['clave'], 2000)
            page.evaluate(JS)
            res = page.evaluate('(q) => MV.liderPage(q)', q)
            if 'error' in res:
                log(f'  {c["clave"]} "{q}" p{pg}: sin datos ({res["error"]})', fh)
                break
            filas += res['items']
            vistos += len(res['items'])
            log(f'  {c["clave"]} "{q}" p{pg}: {len(res["items"])} productos', fh)
            if not res['items'] or not res.get('total') or vistos >= res['total']:
                break
    return filas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--solo', help='cadenas separadas por coma, ej: jumbo,tottus')
    ap.add_argument('--fecha', default=dt.date.today().isoformat())
    ap.add_argument('--ver', action='store_true', help='abrir el navegador con ventana')
    a = ap.parse_args()

    cadenas = cfg.cadenas()
    if a.solo:
        pedidas = [x.strip() for x in a.solo.split(',') if x.strip()]
        faltan = [x for x in pedidas if x not in cadenas]
        if faltan:
            sys.exit(f'No existen o están apagadas en config/cadenas.yml: {", ".join(faltan)}')
        cadenas = {k: cadenas[k] for k in pedidas}
    if not cadenas:
        sys.exit('No hay cadenas activas en config/cadenas.yml.')
    qs = cfg.busquedas()

    out = ROOT / 'raw' / a.fecha
    out.mkdir(parents=True, exist_ok=True)
    (ROOT / 'logs').mkdir(exist_ok=True)
    resumen = {}
    with open(ROOT / 'logs' / f'{a.fecha}.log', 'a', encoding='utf-8') as fh, sync_playwright() as p:
        log(f'Búsquedas ({len(qs)}): {", ".join(qs)}', fh)
        browser = p.chromium.launch(headless=not a.ver)
        for clave, c in cadenas.items():
            # un contexto (navegador limpio) por cadena, para que una no afecte a la otra
            ctx = browser.new_context(locale='es-CL', timezone_id='America/Santiago',
                                      viewport={'width': 1280, 'height': 900})
            page = ctx.new_page()
            try:
                log(f'{clave}: leyendo…', fh)
                if c['forma'] == 'pedir':
                    filas = leer_pidiendo(page, c, qs, fh)
                else:
                    filas = leer_navegando(page, c, qs, fh)
                if not filas:
                    raise RuntimeError(f'{clave}: 0 productos (¿cambió el sitio?)')
                (out / f'{clave}.json').write_text(json.dumps(filas, ensure_ascii=False, indent=0), encoding='utf-8')
                resumen[clave] = f'OK {len(filas)} productos'
                log(f'{clave}: OK {len(filas)} productos', fh)
            except Bloqueado as e:
                resumen[clave] = 'BLOQUEADA'
                log(str(e), fh)
            except Exception as e:
                resumen[clave] = f'FALLÓ ({e})'
                log(f'{clave}: FALLÓ -> {e}', fh)
                fh.write(traceback.format_exc() + '\n')
            finally:
                ctx.close()
            time.sleep(2)
        browser.close()
        log('Resumen: ' + ' | '.join(f'{k}: {v}' for k, v in resumen.items()), fh)
    (out / '_resumen.json').write_text(json.dumps(resumen, ensure_ascii=False, indent=1), encoding='utf-8')
    ok = sum(1 for v in resumen.values() if v.startswith('OK'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
