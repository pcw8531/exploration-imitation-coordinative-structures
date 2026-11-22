# -*- coding: utf-8 -*-
"""Download only the sensor files of MultiSenseBadminton, without the videos.

Seong et al. 2024, Scientific Data 11:343, data on figshare (collection 10.6084/m9.figshare.c.6725706,
CC0). The three data archives hold 51 sensor files (HDF5, 6.55 GB as packed, 12.04 GB unpacked) and
225 videos (60.9 GB). This script copies the 51 sensor files out of the archives by byte range, each
into a small zip of its own exactly as it is packed in the original archive, and checks every one
against the checksum (CRC-32) and size the original archive records for it. The videos are never
touched.

Usage (Windows, Miniforge Prompt, in the folder that holds this script):
    python msb_fetch.py
Options:
    --workers 8    number of files downloaded at the same time (default 8)
    --yes          start without asking

The files go to a new folder MSB_hdf5 beside this script, one subfolder per participant, with a
manifest of what was saved. If the run stops for any reason, run the same command again. Files that
are already complete and checked are skipped, and unfinished ones start again. Nothing outside
MSB_hdf5 is changed. Needs only Python 3.8 or later, no extra packages.
"""
import argparse
import csv
import io
import os
import shutil
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

ARCHIVES = [  # name, figshare file id, size in bytes (figshare API, 28 October 2026)
    ('Data Archive Part1.zip', 44975182, 20314877849),
    ('Data Archive Part2.zip', 44974657, 21808572286),
    ('Data Archive Part3.zip', 44974897, 25360188745),
]
EXPECTED_FILES = 51
BASE = os.environ.get('MSB_BASE', 'https://ndownloader.figshare.com/files/')
HEADERS = {'User-Agent': 'Mozilla/5.0 (msb-fetch; research data access)'}
MiB = 1 << 20
CHUNK = 16 * MiB
STOP = threading.Event()
LOCK = threading.Lock()


def log(*a):
    with LOCK:
        print(*a, flush=True)


class RangeRefused(RuntimeError):
    pass


class Remote(io.RawIOBase):
    """Read-only, seekable view of one remote archive that fetches only the byte ranges asked for.

    Every request carries a Range header, and any answer other than 206 Partial Content stops at
    once, so a server that ignores ranges can never start a 20 GB transfer.
    """

    def __init__(self, file_id, size):
        super().__init__()
        self.src = BASE + str(file_id)
        self.size = int(size)
        self.pos = 0
        self.url = None
        self._resolve()

    def _get(self, url, start, end):
        req = urllib.request.Request(url, headers=dict(HEADERS, Range='bytes=%d-%d' % (start, end)))
        r = urllib.request.urlopen(req, timeout=180)
        if r.status != 206:
            r.close()
            raise RangeRefused('the server answered %s instead of 206 to a byte range request; stopped '
                               'before any large transfer' % r.status)
        return r

    def _resolve(self):
        last = None
        for attempt in range(6):
            try:
                r = self._get(self.src, 0, 0)
                try:
                    total = int(r.headers.get('Content-Range', '/-1').rsplit('/', 1)[1])
                    r.read()
                finally:
                    r.close()
                if total != self.size:
                    raise RuntimeError('size on the server %d differs from the expected %d' % (total, self.size))
                self.url = r.geturl()      # the signed storage address after the redirect
                return
            except RangeRefused:
                raise
            except (urllib.error.URLError, OSError) as e:
                last = e
                time.sleep(min(60, 2 ** attempt))
        raise IOError('could not reach the archive: %s' % last)

    def fetch(self, start, end):
        """Bytes start..end inclusive, with retries and a fresh signed address when it expires."""
        last = None
        for attempt in range(6):
            if STOP.is_set():
                raise KeyboardInterrupt
            try:
                r = self._get(self.url, start, end)
                try:
                    data = r.read()
                finally:
                    r.close()
                if len(data) != end - start + 1:
                    raise IOError('short read %d of %d bytes' % (len(data), end - start + 1))
                return data
            except RangeRefused:
                raise
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (400, 401, 403):
                    try:
                        self._resolve()
                    except Exception as e2:
                        last = e2
            except (urllib.error.URLError, OSError) as e:
                last = e
            time.sleep(min(60, 2 ** attempt))
        raise IOError('failed to read bytes %d-%d after 6 attempts: %s' % (start, end, last))

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def readinto(self, buf):
        n = min(len(buf), max(0, self.size - self.pos))
        if n == 0:
            return 0
        data = self.fetch(self.pos, self.pos + n - 1)
        memoryview(buf)[:n] = data
        self.pos += n
        return n


def member_data_offset(remote, info):
    """Offset of a member's packed data, from its local header (30 bytes plus name and extra field)."""
    head = remote.fetch(info.header_offset, info.header_offset + 29)
    if head[:4] != b'PK\x03\x04':
        raise IOError('no local header at %d' % info.header_offset)
    return info.header_offset + 30 + int.from_bytes(head[26:28], 'little') + int.from_bytes(head[28:30], 'little')


def dos_stamp(dt):
    y, mo, d, h, mi, s = dt
    return (h << 11) | (mi << 5) | (s // 2), ((max(1980, y) - 1980) << 9) | (mo << 5) | d


class Progress:
    def __init__(self, total_bytes, total_files):
        self.total, self.files_total = total_bytes, total_files
        self.done = 0
        self.files = 0
        self.t0 = time.time()

    def add(self, n):
        with LOCK:
            self.done += n

    def line(self):
        el = max(1e-6, time.time() - self.t0)
        rate = self.done / el
        left = (self.total - self.done) / rate if rate > 0 else float('nan')
        return ('%d of %d files, %.2f of %.2f GB, %.1f MB/s, about %s left'
                % (self.files, self.files_total, self.done / 1e9, self.total / 1e9, rate / MiB,
                   ('%d min' % round(left / 60)) if left == left else '?'))


def fetch_member(archive, info, dest, progress):
    """Copy one packed member into its own zip at dest, checking CRC-32 and size on the way."""
    name, fid, size = archive
    remote = Remote(fid, size)
    start = member_data_offset(remote, info)
    inner = os.path.basename(info.filename).encode('ascii')
    if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise IOError('unexpected zip method %d' % info.compress_type)
    if max(info.compress_size, info.file_size) >= 0xFFFFFFFF:
        raise IOError('member too large for a plain zip')
    dtime, ddate = dos_stamp(info.date_time)
    tmp = dest + '.part'
    unz = zlib.decompressobj(-15) if info.compress_type == zipfile.ZIP_DEFLATED else None
    crc, usize = 0, 0
    t0 = time.time()
    with open(tmp, 'wb') as fh:
        fh.write(struct.pack('<IHHHHHIIIHH', 0x04034b50, 20, 0, info.compress_type, dtime, ddate,
                             info.CRC, info.compress_size, info.file_size, len(inner), 0) + inner)
        pos, end = start, start + info.compress_size - 1
        while pos <= end:
            b = min(end, pos + CHUNK - 1)
            data = remote.fetch(pos, b)
            fh.write(data)
            out = unz.decompress(data) if unz else data
            crc = zlib.crc32(out, crc)
            usize += len(out)
            progress.add(len(data))
            pos = b + 1
        if unz:
            out = unz.flush()
            crc = zlib.crc32(out, crc)
            usize += len(out)
        if usize != info.file_size or (crc & 0xFFFFFFFF) != info.CRC:
            raise IOError('check failed for %s: size %d of %d, crc %08x of %08x'
                          % (info.filename, usize, info.file_size, crc & 0xFFFFFFFF, info.CRC))
        cd_offset = fh.tell()
        cd = struct.pack('<IHHHHHHIIIHHHHHII', 0x02014b50, 20, 20, 0, info.compress_type, dtime, ddate,
                         info.CRC, info.compress_size, info.file_size, len(inner), 0, 0, 0, 0, 0, 0) + inner
        fh.write(cd)
        fh.write(struct.pack('<IHHHHIIH', 0x06054b50, 0, 0, 1, 1, len(cd), cd_offset, 0))
    with zipfile.ZipFile(tmp) as z:       # the new zip must open and list exactly one member
        i = z.infolist()
        assert len(i) == 1 and i[0].CRC == info.CRC and i[0].file_size == info.file_size
    os.replace(tmp, dest)
    return time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--yes', action='store_true')
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(here, 'MSB_hdf5')
    os.makedirs(out, exist_ok=True)

    log('Reading the table of contents of the three archives ...')
    jobs = []
    for arch in ARCHIVES:
        z = zipfile.ZipFile(Remote(arch[1], arch[2]))
        for info in z.infolist():
            if info.filename.lower().endswith('.hdf5'):
                sub = os.path.basename(os.path.dirname(info.filename))
                dest = os.path.join(out, sub, os.path.basename(info.filename) + '.zip')
                jobs.append((arch, info, dest))
    if len(jobs) != EXPECTED_FILES:
        log('Warning: found %d sensor files, expected %d.' % (len(jobs), EXPECTED_FILES))

    def complete(dest, info):
        if not os.path.exists(dest):
            return False
        try:
            with zipfile.ZipFile(dest) as z:
                i = z.infolist()
                return len(i) == 1 and i[0].CRC == info.CRC and i[0].file_size == info.file_size
        except Exception:
            return False

    todo = [j for j in jobs if not complete(j[2], j[1])]
    for arch, info, dest in jobs:                          # leftovers of an earlier, stopped run
        if os.path.exists(dest + '.part') and (arch, info, dest) not in todo:
            os.remove(dest + '.part')
    todo.sort(key=lambda j: -j[1].compress_size)          # largest first keeps the workers busy
    need = sum(j[1].compress_size for j in todo)
    free = shutil.disk_usage(out).free
    log('%d sensor files in the archives, %d already complete, %d to download: %.2f GB.'
        % (len(jobs), len(jobs) - len(todo), len(todo), need / 1e9))
    log('Saving to %s (%.0f GB free on this drive).' % (out, free / 1e9))
    if free < need + 2e9:
        log('Not enough free space. Please free %.1f GB and run again.' % ((need + 2e9 - free) / 1e9))
        return 1
    if not todo:
        log('Nothing left to download.')
    elif not args.yes:
        ans = input('Type y and press Enter to start, or just Enter to cancel: ').strip().lower()
        if ans not in ('y', 'yes'):
            log('Cancelled. Nothing was downloaded.')
            return 0

    progress = Progress(need, len(todo))
    results = OrderedDict()

    def run(job):
        arch, info, dest = job
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            sec = fetch_member(arch, info, dest, progress)
            with LOCK:
                progress.files += 1
            results[info.filename] = ('ok', sec)
            log('  saved %s (%.0f MB, %.0f s)' % (os.path.basename(dest), info.compress_size / 1e6, sec))
        except KeyboardInterrupt:
            results[info.filename] = ('stopped', 0)
        except Exception as e:
            results[info.filename] = ('failed: %s' % e, 0)
            log('  FAILED %s: %s' % (os.path.basename(dest), e))
            try:
                os.remove(dest + '.part')
            except OSError:
                pass

    if todo:
        pool = ThreadPoolExecutor(max_workers=max(1, args.workers))
        futures = [pool.submit(run, j) for j in todo]
        last = 0.0
        try:
            while not all(f.done() for f in futures):
                time.sleep(1)
                if time.time() - last > 30:
                    log(progress.line())
                    last = time.time()
        except KeyboardInterrupt:
            STOP.set()
            log('Stopping. Run the same command again later to continue.')
        pool.shutdown(wait=True)
        log(progress.line())

    rows = []
    for arch, info, dest in jobs:
        ok = complete(dest, info)
        rows.append(OrderedDict(participant=os.path.basename(os.path.dirname(dest)),
                                file=os.path.relpath(dest, out), archive=arch[0], member=info.filename,
                                packed_bytes=info.compress_size, unpacked_bytes=info.file_size,
                                crc32=format(info.CRC, '08x'), complete=ok))
    with open(os.path.join(out, 'fetch_manifest.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    n_ok = sum(r['complete'] for r in rows)
    if n_ok == len(rows):
        log('Done. All %d sensor files are saved and checked in %s.' % (n_ok, out))
        return 0
    log('%d of %d files are complete. Run the same command again to fetch the rest.' % (n_ok, len(rows)))
    return 1


if __name__ == '__main__':
    sys.exit(main())
