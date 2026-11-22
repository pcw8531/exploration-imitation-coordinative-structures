# -*- coding: utf-8 -*-
"""Look inside the MultiSenseBadminton archives without downloading them.

Seong et al. 2024, Scientific Data 11:343, data on figshare (collection 10.6084/m9.figshare.c.6725706,
CC0). The three data archives are 20.3, 21.8 and 25.4 GB because each one bundles the videos with the
sensor files. This script reads only the table of contents at the end of each zip archive, saves the
0.8 MB documentation archive, opens one sensor file in place to record how its streams are stored, and
times the connection. It transfers a few tens of MB in total and takes a minute or two.

Usage (Windows, from the folder where the outputs should go):
    python msb_probe.py
or
    python msb_probe.py "D:\\some\\new\\folder"

Needs Python 3.8 or later. numpy and h5py are used for the one sensor file; without them the script
still lists the archives and saves the documentation. Install with  pip install h5py  if needed.

The script only creates a new folder MSB_probe (or MSB_probe_2, ...) and writes into it. It changes
nothing else on the computer.
"""
import csv
import hashlib
import io
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections import OrderedDict

ARCHIVES = [  # name, figshare file id, size in bytes, md5 (figshare API, 28 October 2026)
    ('Data Archive Part1.zip', 44975182, 20314877849, '6179d8f7b99189aafc38cb1d6b0a850c'),
    ('Data Archive Part2.zip', 44974657, 21808572286, '7c07cacf7b6e68ab302196f52b22ba78'),
    ('Data Archive Part3.zip', 44974897, 25360188745, '9f9b7da4d441a59d79b58b124947df53'),
]
DOCS = ('Documentations.zip', 44974654, 837202, '59caa69f66fdcf92154073f9915f8c1e')
BASE = os.environ.get('MSB_BASE', 'https://ndownloader.figshare.com/files/')
HEADERS = {'User-Agent': 'Mozilla/5.0 (msb-probe; research data access)'}
MiB = 1 << 20


def log(*a):
    print(*a, flush=True)


class RangeRefused(RuntimeError):
    pass


class RemoteFile(io.RawIOBase):
    """A read-only, seekable view of a remote file that fetches only the byte ranges it is asked for.

    Every request carries a Range header, and any answer other than 206 Partial Content stops the
    script at once, so a server that ignores ranges can never start a 20 GB transfer.
    """

    def __init__(self, file_id, size, block=MiB, cache_blocks=128):
        super().__init__()
        self.src = BASE + str(file_id)
        self.size = int(size)
        self.block = block
        self.cache = OrderedDict()
        self.cache_blocks = cache_blocks
        self.pos = 0
        self.bytes = 0
        self.requests = 0
        self.url = None
        self._resolve()

    def _get(self, url, start, end):
        req = urllib.request.Request(url, headers=dict(HEADERS, Range='bytes=%d-%d' % (start, end)))
        r = urllib.request.urlopen(req, timeout=120)
        if r.status != 206:
            r.close()
            raise RangeRefused('the server answered %s instead of 206 to a byte range request; stopped '
                               'before any large transfer' % r.status)
        return r

    def _resolve(self):
        r = self._get(self.src, 0, 0)
        try:
            total = int(r.headers.get('Content-Range', '/-1').rsplit('/', 1)[1])
            r.read()
        finally:
            r.close()
        if total != self.size:
            raise RuntimeError('size on the server %d differs from the expected %d' % (total, self.size))
        self.url = r.geturl()      # the signed storage address after the redirect

    def fetch(self, start, end):
        """Bytes start..end inclusive, with retries and a fresh signed address when it expires."""
        last = None
        for attempt in range(5):
            try:
                r = self._get(self.url, start, end)
                try:
                    data = r.read()
                finally:
                    r.close()
                if len(data) != end - start + 1:
                    raise IOError('short read %d of %d bytes' % (len(data), end - start + 1))
                self.bytes += len(data)
                self.requests += 1
                return data
            except RangeRefused:
                raise
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (400, 401, 403):
                    self._resolve()
            except (urllib.error.URLError, OSError) as e:
                last = e
            time.sleep(min(30, 2 ** attempt))
        raise IOError('failed to read bytes %d-%d after 5 attempts: %s' % (start, end, last))

    # io.RawIOBase interface
    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        elif whence == 2:
            self.pos = self.size + offset
        if self.pos < 0:
            raise ValueError('negative seek position')
        return self.pos

    def _blocks(self, first, last):
        """Make sure blocks first..last are cached, fetching each run of missing blocks in one request."""
        missing = [b for b in range(first, last + 1) if b not in self.cache]
        runs, run = [], []
        for b in missing:
            if run and (b != run[-1] + 1 or len(run) * self.block >= 32 * MiB):
                runs.append(run)
                run = []
            run.append(b)
        if run:
            runs.append(run)
        for run in runs:
            start = run[0] * self.block
            end = min(self.size, (run[-1] + 1) * self.block) - 1
            data = self.fetch(start, end)
            for i, b in enumerate(run):
                self.cache[b] = data[i * self.block:(i + 1) * self.block]
        for b in range(first, last + 1):
            self.cache.move_to_end(b)
        while len(self.cache) > max(self.cache_blocks, last - first + 1):
            self.cache.popitem(last=False)

    def readinto(self, buf):
        n = min(len(buf), max(0, self.size - self.pos))
        if n == 0:
            return 0
        first, last = self.pos // self.block, (self.pos + n - 1) // self.block
        self._blocks(first, last)
        view = memoryview(buf)
        got = 0
        while got < n:
            b = (self.pos + got) // self.block
            off = self.pos + got - b * self.block
            chunk = self.cache[b]
            take = min(n - got, len(chunk) - off)
            view[got:got + take] = chunk[off:off + take]
            got += take
        self.pos += n
        return n


class Slice(io.RawIOBase):
    """One stored member of a remote zip archive, seen as a file of its own."""

    def __init__(self, base, start, length):
        super().__init__()
        self.base, self.start, self.length, self.pos = base, start, length, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.length + offset}[whence]
        return self.pos

    def readinto(self, buf):
        n = min(len(buf), max(0, self.length - self.pos))
        if n == 0:
            return 0
        self.base.seek(self.start + self.pos)
        got = self.base.readinto(memoryview(buf)[:n])
        self.pos += got
        return got


def member_data_offset(remote, info):
    """Offset of a member's data, read from its local header (30 bytes plus name and extra field)."""
    remote.seek(info.header_offset)
    head = remote.read(30)
    if head[:4] != b'PK\x03\x04':
        raise IOError('no local header at %d' % info.header_offset)
    n_name = int.from_bytes(head[26:28], 'little')
    n_extra = int.from_bytes(head[28:30], 'little')
    return info.header_offset + 30 + n_name + n_extra


def new_out_dir(parent):
    for k in range(1, 100):
        d = os.path.join(parent, 'MSB_probe' if k == 1 else 'MSB_probe_%d' % k)
        if not os.path.exists(d):
            os.makedirs(d)
            return d
    raise RuntimeError('no free folder name')


def describe_hdf5(fileobj, report):
    import h5py
    import numpy as np
    rows = []
    with h5py.File(fileobj, 'r') as f:
        report['root_attrs'] = {k: str(v)[:400] for k, v in f.attrs.items()}

        def visit(name, obj):
            if isinstance(obj, h5py.Group):
                if obj.attrs:
                    report.setdefault('group_attrs', {})[name] = {k: str(v)[:400] for k, v in obj.attrs.items()}
                return
            plist = obj.id.get_create_plist()
            layout = {0: 'compact', 1: 'contiguous', 2: 'chunked'}.get(plist.get_layout(), str(plist.get_layout()))
            row = OrderedDict(path=name, shape=str(obj.shape), dtype=str(obj.dtype), layout=layout,
                              chunks=str(obj.chunks), compression=str(obj.compression),
                              storage_bytes=int(obj.id.get_storage_size()))
            if name.endswith('time_s') and obj.shape and obj.shape[0] > 1:
                t0, t1 = float(np.squeeze(obj[0])), float(np.squeeze(obj[-1]))
                row['t_first'], row['t_last'] = repr(t0), repr(t1)
                row['rate_hz'] = '%.3f' % ((obj.shape[0] - 1) / (t1 - t0)) if t1 > t0 else ''
            rows.append(row)
        f.visititems(visit)
    return rows


def main():
    parent = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    out = new_out_dir(parent)
    report = OrderedDict(started=time.strftime('%Y-%m-%d %H:%M:%S'), python=sys.version.split()[0],
                         platform=platform.platform(), out=out)
    log('Writing to', out)

    # 1. The documentation archive, in full (0.8 MB), checked against the figshare md5
    name, fid, size, md5 = DOCS
    docs = RemoteFile(fid, size)
    data = docs.fetch(0, size - 1)
    ok = hashlib.md5(data).hexdigest() == md5
    with open(os.path.join(out, name), 'wb') as fh:
        fh.write(data)
    report['documentations'] = dict(file=name, bytes=len(data), md5_ok=ok,
                                    members=zipfile.ZipFile(io.BytesIO(data)).namelist())
    log('Saved %s (%d bytes, md5 %s)' % (name, len(data), 'ok' if ok else 'MISMATCH'))

    # 2. The table of contents of each data archive
    rows, remotes = [], {}
    for name, fid, size, md5 in ARCHIVES:
        rf = RemoteFile(fid, size)
        z = zipfile.ZipFile(rf)
        for i in z.infolist():
            if i.is_dir():
                continue
            rows.append(OrderedDict(archive=name, member=i.filename, method=i.compress_type,
                                    compressed=i.compress_size, size=i.file_size,
                                    header_offset=i.header_offset, crc=format(i.CRC, '08x')))
        remotes[name] = (rf, z)
        log('%s: %d members, %.1f MB read so far' % (name, len(z.infolist()), rf.bytes / MiB))
    with open(os.path.join(out, 'archive_members.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    summary = OrderedDict()
    for r in rows:
        ext = os.path.splitext(r['member'])[1].lower() or '(none)'
        s = summary.setdefault(ext, OrderedDict(count=0, compressed_GB=0.0, size_GB=0.0, methods=set()))
        s['count'] += 1
        s['compressed_GB'] += r['compressed'] / 1e9
        s['size_GB'] += r['size'] / 1e9
        s['methods'].add(r['method'])
    for s in summary.values():
        s['methods'] = sorted(s['methods'])
        s['compressed_GB'] = round(s['compressed_GB'], 3)
        s['size_GB'] = round(s['size_GB'], 3)
    report['by_extension'] = summary
    for ext, s in summary.items():
        log('  %-8s %4d files  %8.2f GB in the archives  (zip method %s)' % (ext, s['count'], s['compressed_GB'], s['methods']))

    # 3. One sensor file opened in place, if it is stored without zip compression
    h5rows = [r for r in rows if r['member'].lower().endswith(('.hdf5', '.h5'))]
    if h5rows:
        pick = sorted(h5rows, key=lambda r: r['size'])[len(h5rows) // 2]   # a typical file
        report['hdf5_probe'] = OrderedDict(archive=pick['archive'], member=pick['member'], size=pick['size'],
                                           method=pick['method'])
        rf, z = remotes[pick['archive']]
        if pick['method'] == zipfile.ZIP_STORED:
            try:
                before = rf.bytes
                start = member_data_offset(rf, z.getinfo(pick['member']))
                h5 = describe_hdf5(Slice(rf, start, pick['size']), report['hdf5_probe'])
                with open(os.path.join(out, 'hdf5_structure.csv'), 'w', newline='', encoding='utf-8') as fh:
                    w = csv.DictWriter(fh, fieldnames=sorted({k for r in h5 for k in r}, key=lambda k: (
                        ['path', 'shape', 'dtype', 'layout', 'chunks', 'compression', 'storage_bytes',
                         't_first', 't_last', 'rate_hz'].index(k))))
                    w.writeheader()
                    w.writerows(h5)
                report['hdf5_probe']['datasets'] = len(h5)
                report['hdf5_probe']['MB_read'] = round((rf.bytes - before) / MiB, 2)
                log('Opened %s in place: %d datasets, %.1f MB read' % (pick['member'], len(h5), (rf.bytes - before) / MiB))
            except ImportError as e:
                report['hdf5_probe']['error'] = 'h5py or numpy missing (%s); run  pip install h5py' % e
                log(report['hdf5_probe']['error'])
            except Exception as e:  # keep the rest of the report
                report['hdf5_probe']['error'] = '%s: %s' % (type(e).__name__, e)
                log('Could not open the sensor file in place:', report['hdf5_probe']['error'])
        else:
            report['hdf5_probe']['note'] = 'compressed inside the zip, cannot be opened in place'
            log('The sensor files are compressed inside the zip archives.')

    # 4. Connection speed: ten small reads and one 32 MB read from the middle of the first archive
    rf = remotes[ARCHIVES[0][0]][0]
    t = time.time()
    for k in range(10):
        rf.fetch(rf.size // 3 + k * 7919, rf.size // 3 + k * 7919 + 1023)
    lat = (time.time() - t) / 10
    a = rf.size // 2
    b = min(rf.size - 1, a + 32 * MiB - 1)
    t = time.time()
    rf.fetch(a, b)
    rate = (b - a + 1) / MiB / (time.time() - t)
    report['speed'] = dict(seconds_per_small_request=round(lat, 3), MB_per_s=round(rate, 2))
    log('Speed: %.2f s per small request, %.1f MB/s for a large one' % (lat, rate))

    total = sum(rf.bytes for rf, _ in remotes.values()) + docs.bytes
    report['MB_transferred'] = round(total / MiB, 1)
    report['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    with open(os.path.join(out, 'probe_report.json'), 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=1, default=str)
    log('Done. %.1f MB transferred in total. The copied files are in %s.' % (total / MiB, out))


if __name__ == '__main__':
    main()
