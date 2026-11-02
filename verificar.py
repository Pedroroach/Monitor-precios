# -*- coding: utf-8 -*-
"""Compara precios del levantamiento contra la página de cada producto en el sitio de la cadena.

Uso: python verificar.py [fecha] [--n 3]
Para cada cadena que funcionó, abre la ficha de N productos y lee el precio que muestra la ficha
(datos estructurados de la página y el texto visible). Imprime una tabla para revisar.
"""
import argparse, glob, json, os, re
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))


def precios_de_ficha(page):
    datos = page.evaluate('''() => {
      const out = [];
      for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
        try { const j = JSON.parse(s.textContent); const xs = Array.isArray(j) ? j : [j];
          for (const x of xs) { const o = x.offers ? (Array.isArray(x.offers) ? x.offers : [x.offers]) : [];
            for (const of of o) for (const k of ['price','lowPrice','highPrice']) if (of[k] != null) out.push(k + '=' + of[k]); } } catch (e) {}
      }
      const meta = document.querySelector('meta[property="product:price:amount"]');
      if (meta) out.push('meta=' + meta.content);
      const txt = (document.querySelector('main') || document.body).innerText || '';
      const vis = [...txt.matchAll(/\\$\\s?\\d{1,3}(?:\\.\\d{3})+|\\$\\s?\\d{3,4}\\b/g)].slice(0, 4).map(m => m[0].replace(/\\s/g, ''));
      return {estructurado: out, visible: vis};
    }''')
    return datos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('fecha', nargs='?')
    ap.add_argument('--n', type=int, default=3)
    a = ap.parse_args()
    f = os.path.join(ROOT, 'data', a.fecha + '.json') if a.fecha else max(glob.glob(os.path.join(ROOT, 'data', '20*.json')))
    rows = json.load(open(f, encoding='utf-8'))['rows']
    # por cadena, N productos de categorías distintas (para variar)
    elegidos = []
    for cad in dict.fromkeys(r['cadena'] for r in rows):
        cats_vistas = set()
        for r in rows:
            if r['cadena'] == cad and r['url'] and r['p_actual'] and r['cat'] not in cats_vistas:
                elegidos.append(r)
                cats_vistas.add(r['cat'])
                if len(cats_vistas) == a.n:
                    break
    print(f'Verificación contra la ficha del producto ({os.path.basename(f)})')
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(locale='es-CL', timezone_id='America/Santiago')
        page = ctx.new_page()
        for r in elegidos:
            try:
                page.goto(r['url'], wait_until='domcontentloaded', timeout=60000)
                page.wait_for_timeout(4000)
                d = precios_de_ficha(page)
                print(f"VERIF | {r['cadena']} | {r['sku']} | levantamiento: hoy ${r['p_actual']} normal ${r['p_normal']} "
                      f"| ficha estructurada: {', '.join(d['estructurado']) or '-'} | ficha visible: {', '.join(d['visible']) or '-'} | {r['url']}")
            except Exception as e:
                print(f"VERIF | {r['cadena']} | {r['sku']} | no se pudo abrir la ficha: {e}")
        b.close()


if __name__ == '__main__':
    main()
