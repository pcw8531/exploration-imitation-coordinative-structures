# -*- coding: utf-8 -*-
"""Coupling between muscle sites and between joints within each annotated stroke of MultiSenseBadminton.

Seong et al. 2024, Scientific Data 11:343; data on figshare, collection 10.6084/m9.figshare.c.6725706
(CC0). One sensor file holds one participant and one stroke type. For every stroke the annotation file
times, this module cuts the electromyography of 20 sites and the rotation of 21 joints out of the file,
puts every stream on a common 50 Hz grid, and returns the Pearson correlation between sites and between
joints over the stroke.

Streams, as the sensor files store them:
  gforce-lowerarm-emg / emg-values   8 armband channels on the dominant forearm, 8-bit, about 100 Hz in most files
  gforce-upperarm-emg / emg-values   8 armband channels on the dominant upper arm, 8-bit, about 115 Hz in most files
  cgx-aim-leg-emg / emg-values       rectus femoris, vastus medialis, vastus lateralis, biceps femoris of
                                     the dominant leg, about 500 Hz
  pns-joint / quaternion             local rotation of 21 joints, about 60 Hz
The time stamps arrive in packets, several samples sharing one stamp, so each sample is given a time
spread evenly between the stamps where the time changes.

Envelopes. The armband values sit around a mid-scale offset, so each channel is centred on its session
median and rectified. The leg channels carry a direct offset and occasional electrode spikes, so they are
high-passed at 20 Hz on a uniform 450 Hz grid, rectified and clipped at the median plus 20 median
absolute deviations. Every envelope is low-passed at 5 Hz, the cut-off the dataset's own pipeline uses
for the armbands. Joint activity is the angular speed between consecutive unit quaternions, low-passed
at 6 Hz. All filters are fourth-order Butterworth run forward and backward, over the stroke padded by
one second.

Reading the sensor files needs h5py, or the pure-Python pyfive when h5py is not installed.
"""
import numpy as np
from scipy.signal import butter, filtfilt

FS = 50.0           # common grid, Hz
PAD = 1.0           # seconds of padding on each side of a stroke for filtering
JOINTS = ['hip', 'right up leg', 'right leg', 'right foot', 'left up leg', 'left leg', 'left foot', 'spine',
          'spine 1', 'spine 2', 'neck', 'neck 1', 'head', 'right shoulder', 'right arm', 'right forearm',
          'right hand', 'left shoulder', 'left arm', 'left forearm', 'left hand']
EMG_SITES = (['forearm %d' % (i + 1) for i in range(8)] + ['upper arm %d' % (i + 1) for i in range(8)] +
             ['rectus femoris', 'vastus medialis', 'vastus lateralis', 'biceps femoris'])
STREAMS = [('leg', 'cgx-aim-leg-emg', 'emg-values'), ('low', 'gforce-lowerarm-emg', 'emg-values'),
           ('up', 'gforce-upperarm-emg', 'emg-values'), ('quat', 'pns-joint', 'quaternion')]


def open_hdf5(path):
    try:
        import h5py
        return h5py.File(path, 'r')
    except ImportError:
        import pyfive
        return pyfive.File(path)


def repaired_time(t):
    """Packet time stamps to one time per sample, spread evenly between the stamps where time changes."""
    t = np.asarray(t, float).ravel()
    first = np.r_[0, np.nonzero(np.diff(t) > 0)[0] + 1]
    return np.interp(np.arange(t.size), first, t[first])


def load(path):
    f = open_hdf5(path)
    out = {}
    for key, dev, st in STREAMS:
        g = f[dev][st]
        out[key] = (repaired_time(g['time_s'][:]), np.asarray(g['data'][:], float))
    return out


def lowpass(x, fc, fs, order=4):
    b, a = butter(order, fc / (fs / 2), 'low')
    return filtfilt(b, a, x, axis=0)


def highpass(x, fc, fs, order=4):
    b, a = butter(order, fc / (fs / 2), 'high')
    return filtfilt(b, a, x, axis=0)


def on_grid(t, x, grid):
    return np.column_stack([np.interp(grid, t, x[:, j]) for j in range(x.shape[1])])


class Streams:
    """Per-session preparation, then per-stroke cuts on the common grid."""

    def __init__(self, raw):
        self.arm = {}
        for k in ('low', 'up'):
            t, x = raw[k]
            self.arm[k] = (t, np.abs(x - np.median(x, axis=0)))
        t, x = raw['leg']
        self.leg_fs = (t.size - 1) / (t[-1] - t[0])
        self.leg = (t, x)
        t, q = raw['quat']
        q = q.reshape(len(t), 21, 4)
        q = q / np.linalg.norm(q, axis=2, keepdims=True)
        dot = np.clip(np.abs(np.sum(q[1:] * q[:-1], axis=2)), 0, 1)
        dt = np.diff(t)[:, None]
        w = 2 * np.arccos(dot) / np.where(dt > 0, dt, np.nan)
        tm = 0.5 * (t[1:] + t[:-1])
        good = np.isfinite(w).all(1)
        self.joint = (tm[good], w[good])

    def stroke(self, t0, t1):
        """EMG envelopes (samples x 20) and joint speeds (samples x 21) over one stroke, or None."""
        grid = np.arange(t0 - PAD, t1 + PAD, 1 / FS)
        keep = (grid >= t0) & (grid <= t1)
        parts = []
        for k in ('low', 'up'):
            t, x = self.arm[k]
            m = (t >= t0 - PAD - 0.5) & (t <= t1 + PAD + 0.5)
            if m.sum() < 20:
                return None
            parts.append(lowpass(on_grid(t[m], x[m], grid), 5.0, FS))
        t, x = self.leg
        m = (t >= t0 - PAD - 0.5) & (t <= t1 + PAD + 0.5)
        if m.sum() < 200:
            return None
        g2 = np.arange(t0 - PAD - 0.5, t1 + PAD + 0.5, 1 / 450.0)
        y = np.abs(highpass(on_grid(t[m], x[m], g2), 20.0, 450.0))
        cap = np.median(y, 0) + 20 * (np.median(np.abs(y - np.median(y, 0)), 0) + 1e-9)
        y = lowpass(np.minimum(y, cap), 5.0, 450.0)
        parts.append(on_grid(g2, y, grid))
        emg = np.column_stack(parts)[keep]
        t, w = self.joint
        m = (t >= t0 - PAD - 0.5) & (t <= t1 + PAD + 0.5)
        if m.sum() < 30:
            return None
        jnt = lowpass(on_grid(t[m], w[m], grid), 6.0, FS)[keep]
        return emg, jnt


def corr(x):
    """Pearson correlation between columns; a column without variance gives NaN."""
    x = x - x.mean(0)
    s = x.std(0)
    s[s == 0] = np.nan
    z = x / s
    return (z.T @ z) / len(x)


def fisher_mean(rs):
    """Mean of correlation matrices on Fisher's z scale, back to r."""
    z = np.arctanh(np.clip(np.array(rs, float), -0.999999, 0.999999))
    return np.tanh(np.nanmean(z, axis=0))


def compression(W, kind='eig'):
    """Control entropy on eigenvector (or degree) shares of a coupling matrix: H, log2 N - H, shares."""
    W = np.array(W, float)
    np.fill_diagonal(W, 0)
    v = np.abs(np.linalg.eigh(W)[1][:, -1]) if kind == 'eig' else W.sum(1)
    p = v / v.sum()
    q = p[p > 0]
    H = -np.sum(q * np.log2(q))
    return H, np.log2(W.shape[0]) - H, p
