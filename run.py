# -*- coding: utf-8 -*-
"""Levantamiento completo: leer cadenas -> limpiar y calcular $/kg -> Excel.
Uso: python run.py [--solo jumbo,tottus] [--sin-excel]"""
import datetime as dt, os, subprocess, sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
fecha = dt.datetime.now(ZoneInfo('America/Santiago')).date().isoformat()  # fecha de Chile, no del servidor
args = sys.argv[1:]
excel = '--sin-excel' not in args
extra = [a for a in args if a != '--sin-excel']


def paso(nombre, a):
    print(f'\n=== {nombre} ===', flush=True)
    return subprocess.run([PY] + a, cwd=ROOT).returncode


rc = paso('1/3 Leyendo cadenas', ['scraper.py', '--fecha', fecha] + extra)
raw = os.path.join(ROOT, 'raw', fecha)
if not os.path.isdir(raw) or not [f for f in os.listdir(raw) if not f.startswith('_')]:
    sys.exit('No se obtuvo ninguna cadena. Revisa logs/' + fecha + '.log')
if paso('2/3 Limpiando y calculando $/kg', ['process.py', raw]) != 0:
    sys.exit('Falló la limpieza. Revisa el mensaje de arriba.')
if excel:
    paso('3/3 Generando Excel', ['report.py', fecha])
print('\nListo. Log en logs/' + fecha + '.log')
sys.exit(rc)
