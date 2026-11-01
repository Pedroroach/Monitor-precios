# -*- coding: utf-8 -*-
"""Genera el Excel de referencia de precios a partir de data/*.json.

Uso: python report.py            -> reportes/precios-<ultima fecha>.xlsx
     python report.py 2026-10-02 -> reporte de esa fecha
Hojas: Referencia, Por cadena, Marcas, SKUs, Histórico, Notas.
canasta.csv (opcional): lista de URLs de SKUs relevantes; se marcan en la hoja SKUs y
la hoja Referencia agrega un bloque calculado solo con ellos.
"""
import csv, glob, json, os, statistics as st, sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import configuracion as cfg

ROOT = str(cfg.ROOT)
CATS = [p['nombre'] for p in cfg.productos()[0]]
CHAINS = [c['nombre'] for c in cfg.cadenas(solo_activas=False).values()]

F = 'Arial'
H_FILL = PatternFill('solid', fgColor='1F2D3A')
H_FONT = Font(name=F, bold=True, color='FFFFFF', size=10)
B_FONT = Font(name=F, size=10)
BOLD = Font(name=F, size=10, bold=True)
TITLE = Font(name=F, size=14, bold=True)
NOTE = Font(name=F, size=9, italic=True, color='5D6B76')
CAT_FILL = PatternFill('solid', fgColor='E9EEF1')
HI_FILL = PatternFill('solid', fgColor='F3E3E1')
THIN = Border(bottom=Side(style='thin', color='D9E0E5'))
CLP = '"$"#,##0;-"$"#,##0;"-"'


def load(fecha=None):
    files = sorted(glob.glob(os.path.join(ROOT, 'data', '20*.json')))
    if not files:
        sys.exit('No hay datos en data/. Corre primero scraper.py y process.py.')
    snaps = {os.path.basename(f)[:-5]: json.load(open(f, encoding='utf-8'))['rows'] for f in files}  # 'descartados' no va al Excel
    fecha = fecha or max(snaps)
    return fecha, snaps


def canasta():
    p = os.path.join(ROOT, 'canasta.csv')
    if not os.path.exists(p):
        return set()
    with open(p, encoding='utf-8-sig') as fh:
        return {r['url'].strip() for r in csv.DictReader(fh) if r.get('url', '').strip()}


def q(vals, p):
    v = sorted(vals)
    if not v:
        return None
    i = (len(v) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (i - lo))


def header(ws, row, cols, widths=None):
    for j, c in enumerate(cols, 1):
        cell = ws.cell(row=row, column=j, value=c)
        cell.font, cell.fill = H_FONT, H_FILL
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[row].height = 30
    if widths:
        for j, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(j)].width = w


def ref_block(ws, r0, rows, titulo):
    ws.cell(row=r0, column=1, value=titulo).font = BOLD
    r = r0 + 1
    header(ws, r, ['Categoría', 'SKUs', 'Mín $/kg', 'P25 $/kg', 'Mediana $/kg', 'P75 $/kg', 'Máx $/kg',
                   'Mediana pagando oferta $/kg', '% SKUs en promo'])
    for cat in CATS:
        R = [x for x in rows if x['cat'] == cat]
        pn = [x['ppk_normal'] for x in R if x['ppk_normal']]
        pp = [x['ppk_promo_min'] or x['ppk_normal'] for x in R if x['ppk_normal']]
        r += 1
        vals = [cat, len(R), min(pn) if pn else None, q(pn, .25), q(pn, .5), q(pn, .75), max(pn) if pn else None,
                q(pp, .5), (sum(1 for x in R if x['en_promo']) / len(R)) if R else None]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=r, column=j, value=v)
            c.font, c.border = B_FONT, THIN
            if 3 <= j <= 8:
                c.number_format = CLP
            if j == 9:
                c.number_format = '0%'
        ws.cell(row=r, column=5).font = BOLD
        ws.cell(row=r, column=5).fill = HI_FILL
    return r + 2


def main():
    fecha, snaps = load(sys.argv[1] if len(sys.argv) > 1 else None)
    rows = [x for x in snaps[fecha] if x['cat'] in CATS]
    cz = canasta()
    for x in rows:
        x['relevante'] = 'Sí' if x['url'] in cz else ''
    wb = Workbook()

    # ---------- Referencia ----------
    ws = wb.active
    ws.title = 'Referencia'
    ws['A1'] = f'Precios web de supermercados · {fecha}'
    ws['A1'].font = TITLE
    ws['A2'] = ('Precio normal = precio de lista (sin oferta). Referencia de precios retail. '
                'P25–P75 = banda donde está el 50% central de los SKUs.')
    ws['A2'].font = NOTE
    nxt = ref_block(ws, 4, rows, 'Todas las cadenas (' + ', '.join(CHAINS) + ')')
    if cz:
        ref_block(ws, nxt, [x for x in rows if x['relevante']], f'Solo canasta relevante ({len(cz)} SKUs en canasta.csv)')
    for j, w in enumerate([16, 8, 12, 12, 14, 12, 12, 16, 12], 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = 'A6'

    # ---------- Por cadena ----------
    ws = wb.create_sheet('Por cadena')
    header(ws, 1, ['Categoría', 'Cadena', 'SKUs', 'Mín $/kg', 'Mediana $/kg', 'Máx $/kg', 'Mediana pagando oferta $/kg', 'SKUs en promo'],
           [16, 14, 8, 12, 14, 12, 16, 12])
    r = 1
    for cat in CATS:
        for ch in CHAINS:
            R = [x for x in rows if x['cat'] == cat and x['cadena'] == ch and x['ppk_normal']]
            if not R:
                continue
            pn = [x['ppk_normal'] for x in R]
            pp = [x['ppk_promo_min'] or x['ppk_normal'] for x in R]
            r += 1
            for j, v in enumerate([cat, ch, len(R), min(pn), q(pn, .5), max(pn), q(pp, .5), sum(1 for x in R if x['en_promo'])], 1):
                c = ws.cell(row=r, column=j, value=v)
                c.font, c.border = B_FONT, THIN
                if 4 <= j <= 7:
                    c.number_format = CLP
    ws.auto_filter.ref = f'A1:H{r}'
    ws.freeze_panes = 'A2'

    # ---------- Marcas ----------
    ws = wb.create_sheet('Marcas')
    header(ws, 1, ['Categoría', 'Marca', 'SKUs'] + [f'{c} $/kg' for c in CHAINS] + ['Mediana $/kg', 'vs mediana categoría'],
           [16, 22, 7] + [13] * len(CHAINS) + [14, 14])
    r = 1
    for cat in CATS:
        R = [x for x in rows if x['cat'] == cat and x['ppk_normal']]
        if not R:
            continue
        mcat = q([x['ppk_normal'] for x in R], .5)
        marcas = sorted({x['marca'] for x in R}, key=lambda m: q([x['ppk_normal'] for x in R if x['marca'] == m], .5))
        for m in marcas:
            M = [x for x in R if x['marca'] == m]
            r += 1
            vals = [cat, m, len(M)] + [q([x['ppk_normal'] for x in M if x['cadena'] == c], .5) for c in CHAINS]
            vals += [q([x['ppk_normal'] for x in M], .5)]
            for j, v in enumerate(vals, 1):
                c = ws.cell(row=r, column=j, value=v)
                c.font, c.border = B_FONT, THIN
                if j >= 4:
                    c.number_format = CLP
            col_med = get_column_letter(len(vals))
            c = ws.cell(row=r, column=len(vals) + 1, value=f'=IFERROR({col_med}{r}/{mcat}-1,"")')
            c.font, c.number_format, c.border = B_FONT, '+0%;-0%;0%', THIN
    ws.auto_filter.ref = f'A1:{get_column_letter(len(CHAINS) + 5)}{r}'
    ws.freeze_panes = 'C2'

    # ---------- SKUs ----------
    ws = wb.create_sheet('SKUs')
    cols = [('Relevante', 'relevante', 10), ('Categoría', 'cat', 13), ('Cadena', 'cadena', 12), ('Marca', 'marca', 18),
            ('SKU', 'sku', 52), ('Kg envase', 'kg', 9), ('Precio normal', 'p_normal', 12), ('Precio hoy', 'p_actual', 11),
            ('Precio tarjeta', 'p_tarjeta', 11), ('$/kg normal', 'ppk_normal', 12), ('$/kg hoy', 'ppk_actual', 11),
            ('$/kg mejor promo', 'ppk_promo_min', 13), ('Promo', 'promo', 16),
            ('Con stock', 'stock', 9), ('Link', 'url', 40)]
    header(ws, 1, [c[0] for c in cols], [c[2] for c in cols])
    rows_sorted = sorted(rows, key=lambda x: (CATS.index(x['cat']), x['ppk_normal'] or 10**9))
    for i, x in enumerate(rows_sorted, 2):
        for j, (_, k, _) in enumerate(cols, 1):
            v = x.get(k)
            if k == 'stock':
                v = 'Sí' if v else 'No'
            c = ws.cell(row=i, column=j, value=v)
            c.font = B_FONT
            if k in ('p_normal', 'p_actual', 'p_tarjeta', 'ppk_normal', 'ppk_actual', 'ppk_promo_min'):
                c.number_format = CLP
            if k == 'kg':
                c.number_format = '0.000'
            if k == 'url' and v:
                c.hyperlink = v
                c.font = Font(name=F, size=10, color='2F6F8F', underline='single')
    ws.auto_filter.ref = f'A1:{get_column_letter(len(cols))}{len(rows_sorted) + 1}'
    ws.freeze_panes = 'F2'

    # ---------- Histórico ----------
    ws = wb.create_sheet('Histórico')
    fechas = sorted(snaps)
    header(ws, 1, ['Categoría', 'Cadena'] + fechas + (['Var. última semana'] if len(fechas) > 1 else []),
           [16, 14] + [13] * len(fechas) + [14])
    r = 1
    for cat in CATS:
        for ch in CHAINS + ['TOTAL']:
            vals = []
            for f in fechas:
                R = [x['ppk_normal'] for x in snaps[f] if x['cat'] == cat and x['ppk_normal'] and (ch == 'TOTAL' or x['cadena'] == ch)]
                vals.append(q(R, .5))
            if not any(vals):
                continue
            r += 1
            for j, v in enumerate([cat, ch] + vals, 1):
                c = ws.cell(row=r, column=j, value=v)
                c.font = BOLD if ch == 'TOTAL' else B_FONT
                c.border = THIN
                if j > 2:
                    c.number_format = CLP
                if ch == 'TOTAL':
                    c.fill = CAT_FILL
            if len(fechas) > 1:
                a, b = get_column_letter(len(fechas) + 1), get_column_letter(len(fechas) + 2)
                c = ws.cell(row=r, column=len(fechas) + 3, value=f'=IFERROR({b}{r}/{a}{r}-1,"")')
                c.number_format, c.font, c.border = '+0.0%;-0.0%;0.0%', B_FONT, THIN
    ws['A' + str(r + 2)] = 'Mediana $/kg precio normal por levantamiento.'
    ws['A' + str(r + 2)].font = NOTE
    ws.freeze_panes = 'C2'

    # ---------- Notas ----------
    ws = wb.create_sheet('Notas')
    notas = [
        'Cómo leer este archivo',
        'Fuente: sitios web de ' + ', '.join(CHAINS) + ', leídos con un navegador automático. Precio de la ubicación por defecto del sitio (normalmente RM); puede diferir de la tienda en regiones.',
        'Alcance: los productos definidos en config/productos.yml (' + ', '.join(CATS) + ').',
        'Precio normal = precio de lista publicado (tachado cuando hay oferta). Mejor promo = el menor entre precio oferta, precio por pack (5 x $3.000 → unitario) y precio con tarjeta (Tottus CMR).',
        '$/kg: peso declarado por la cadena; si no existe, el peso del nombre. SKUs sin peso identificable no entran a medianas.',
        'Las búsquedas son por palabra clave, no catálogo completo: puede faltar algún SKU. Santa Isabel no expone sus promos "lleva X por $Y".',
        'Mediana, P25 y P75 se calculan en Python al generar el archivo (no son fórmulas). Para marcar SKUs relevantes, agrega su link a canasta.csv.',
    ]
    for i, t in enumerate(notas, 1):
        c = ws.cell(row=i, column=1, value=t)
        c.font = TITLE if i == 1 else B_FONT
        c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.column_dimensions['A'].width = 110

    os.makedirs(os.path.join(ROOT, 'reportes'), exist_ok=True)
    out = os.path.join(ROOT, 'reportes', f'precios-{fecha}.xlsx')
    wb.save(out)
    print('Excel:', out)


if __name__ == '__main__':
    main()
