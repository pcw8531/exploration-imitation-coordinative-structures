"""Rerun the notebooks and compare what they print with what is stored in them.

Usage, from the top folder of the repository:

    python src/verify_notebooks.py                                   all ten notebooks, about an hour and a half
    python src/verify_notebooks.py EEI_fig1_problem_and_checks.ipynb  one or more notebooks by name

The notebooks are read from the folder notebooks and run there, whatever folder the script is started from.

Each notebook is run cell by cell in one Python process of its own. Every line a cell prints is compared
with the line stored in the notebook. Lines that report a running time are compared without the time.
Figures are drawn but not shown, and the notebooks of Figs. 1, 5 and 6 write their panel files to the
folder notebooks/figs. The script needs only the packages in requirements.txt and exits with status 1 if any
printed line differs.
"""
import contextlib
import glob
import io
import json
import os
import re
import subprocess
import sys
import time

ORDER = ['EEI_fig1_problem_and_checks.ipynb', 'EEI_fig2_topology.ipynb', 'EEI_fig3_control_entropy.ipynb',
         'EEI_fig4_mechanism.ipynb', 'EEI_fig5_game.ipynb', 'EEI_fig6_budget.ipynb', 'EEI_supp1_copying.ipynb',
         'EEI_supp2_lineage.ipynb', 'EEI_supp3_hypotheses.ipynb', 'EEI_supp4_regime_map.ipynb']
NOTEBOOKS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'notebooks')
TIMING = re.compile(r'\bin \d+(\.\d+)?\s?s\b')


def lines(text):
    return [TIMING.sub('in T s', line.rstrip()) for line in text.strip().split('\n')]


def run_one(path):
    """Run the code cells of one notebook in order and return the printed lines that differ."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.show = lambda *args, **kwargs: plt.close('all')
    notebook = json.load(open(path, encoding='utf8'))
    names = {'__name__': '__main__'}
    different, number = [], 0
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        number += 1
        stored = ''.join(''.join(out.get('text', '')) for out in cell.get('outputs', [])
                         if out.get('output_type') == 'stream' and out.get('name') == 'stdout')
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            exec(compile(''.join(cell['source']), f'<{path}, code cell {number}>', 'exec'), names)
        old, new = lines(stored), lines(printed.getvalue())
        if len(old) != len(new):
            different.append((number, f'{len(old)} lines stored', f'{len(new)} lines printed'))
        different += [(number, a, b) for a, b in zip(old, new) if a != b]
    return different


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    os.chdir(NOTEBOOKS)
    if len(sys.argv) == 3 and sys.argv[1] == '--one':
        found = run_one(sys.argv[2])
        for number, a, b in found:
            print(f'  code cell {number}\n    stored:  {a}\n    printed: {b}')
        sys.exit(1 if found else 0)
    chosen = [os.path.basename(name) for name in sys.argv[1:]] or [name for name in ORDER if os.path.exists(name)]
    missing = [name for name in chosen if not os.path.exists(name)]
    if missing:
        sys.exit('not found: ' + ', '.join(missing) + '. The folder notebooks holds '
                 + ', '.join(sorted(glob.glob('*.ipynb'))))
    failed = []
    for name in chosen:
        start = time.time()
        result = subprocess.run([sys.executable, os.path.abspath(__file__), '--one', name], capture_output=True,
                                text=True, encoding='utf-8', errors='replace',
                                env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        minutes = (time.time() - start) / 60
        if result.returncode == 0:
            print(f'{name}: every printed line is the same ({minutes:.1f} min)', flush=True)
        else:
            failed.append(name)
            print(f'{name}: DIFFERENT ({minutes:.1f} min)\n{result.stdout}{result.stderr[-2000:]}', flush=True)
    print('all notebooks reproduce their stored output' if not failed else 'differences in: ' + ', '.join(failed))
    sys.exit(1 if failed else 0)
