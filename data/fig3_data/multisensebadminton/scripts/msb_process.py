# -*- coding: utf-8 -*-
"""Per-stroke coupling matrices for every MultiSenseBadminton sensor file.

Usage:
    python msb_process.py DOCS_DIR OUT_DIR file1.hdf5.zip [file2.hdf5.zip ...]

DOCS_DIR holds 'Annotation Data File.xlsx' from the dataset's Documentations archive. Each input is one
sensor file as msb_fetch.py saves it, a zip holding one HDF5 file, or the HDF5 file itself. For each file
the script writes OUT_DIR/<file name>.npz with

    sub, fname, type, skill   participant, file, stroke type and coach-rated skill from the annotation
    n, t0, t1, num            number of strokes kept, their start and stop times (Unix s), stroke numbers
    RE                        n x 20 x 20 correlation between the 20 EMG sites within each stroke
    RJ                        n x 21 x 21 correlation between the angular speeds of the 21 joints
    rates                     mean sampling rate of the leg EMG, forearm EMG, upper-arm EMG and joints

A stroke is kept when it lies at least 1.5 s inside every stream of the file and every channel varies
within it. Sub05 recorded a calibration-only file, which has no strokes. Needs NumPy, SciPy, pandas
with openpyxl, and h5py or pyfive.
"""
import os
import sys
import tempfile
import time
import zipfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import msb_coupling as mc

COLS = ['sub', 't0', 't1', 'num', 'type', 'skill', 'h', 'v', 'hit', 'sound', 'h1', 'h2', 'h3', 's1', 's2', 's3']


def annotation(docs):
    A = pd.read_excel(os.path.join(docs, 'Annotation Data File.xlsx'))
    A.columns = COLS
    return A


def process(path, A, outdir):
    name = os.path.basename(path)
    base = name[:-4] if name.endswith('.zip') else name
    out = os.path.join(outdir, base.replace('.hdf5', '.npz'))
    if os.path.exists(out):
        return 'exists'
    sub = base.split('_')[-1].split('.')[0]
    if name.endswith('.zip'):
        with tempfile.TemporaryDirectory(dir=outdir) as td:
            with zipfile.ZipFile(path) as z:
                if z.testzip() is not None:
                    raise IOError('damaged zip: ' + name)
                z.extractall(td)
            raw = mc.load(os.path.join(td, base))
    else:
        raw = mc.load(path)
    S = mc.Streams(raw)
    lo = max(raw[k][0][0] for k in raw)
    hi = min(raw[k][0][-1] for k in raw)
    s = A[(A['sub'] == sub) & (A.t0 > lo + 1.5) & (A.t1 < hi - 1.5)].sort_values('t0')
    if len(s) == 0:
        np.savez_compressed(out, sub=sub, fname=base, n=0)
        return 'no strokes'
    RE, RJ, keep = [], [], []
    for i, r in enumerate(s.itertuples()):
        res = S.stroke(r.t0, r.t1)
        if res is None:
            continue
        ce, cj = mc.corr(res[0]), mc.corr(res[1])
        if not (np.isfinite(ce).all() and np.isfinite(cj).all()):
            continue
        RE.append(ce)
        RJ.append(cj)
        keep.append(i)
    s = s.iloc[keep]
    types = list(s['type'].unique())
    rates = [(raw[k][0].size - 1) / (raw[k][0][-1] - raw[k][0][0]) for k in ('leg', 'low', 'up', 'quat')]
    np.savez_compressed(out, sub=sub, fname=base, type='|'.join(types), skill=s['skill'].iloc[0], n=len(s),
                        t0=s.t0.values, t1=s.t1.values, num=s.num.values, RE=np.array(RE, np.float32),
                        RJ=np.array(RJ, np.float32), rates=np.array(rates))
    return '%s %s %s, %d strokes' % (sub, '|'.join(types), s['skill'].iloc[0], len(s))


if __name__ == '__main__':
    docs, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    A = annotation(docs)
    for p in sys.argv[3:]:
        t = time.time()
        try:
            msg = process(p, A, outdir)
        except Exception as e:
            msg = 'ERROR %s: %s' % (type(e).__name__, e)
        print(os.path.basename(p)[:64], msg, '%.1f s' % (time.time() - t), flush=True)
