"""Railroader's AudioUtilities.Loopify, offline: second half of the clip + its start, the join crossfaded over 4096 samples.
usage: loopify_wav.py <in.wav> <out.wav> [--asis]   (--asis: copy unchanged, 16-bit PCM)"""
import sys, wave, numpy as np
src, dst = sys.argv[1], sys.argv[2]
w = wave.open(src, 'rb'); ch, sw, fr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
raw = w.readframes(n); w.close()
if sw == 2: a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
elif sw == 4: a = np.frombuffer(raw, np.int32).astype(np.float32) / 2147483648
else: raise SystemExit(f'sample width {sw}')
a = a.reshape(-1, ch)
if '--asis' not in sys.argv:
    num = n if n % 2 == 0 else n - 1
    X = 4096
    half = num // 2 - X
    out = np.zeros((half * 2 + X, ch), np.float32)
    out[:half] = a[num // 2:num // 2 + half]
    out[half + X:] = a[X:X + half]
    t = (np.arange(X) / X)[:, None]
    out[half:half + X] = a[num - X:num] * (1 - t) + a[:X] * t
    a = out
o = wave.open(dst, 'wb'); o.setnchannels(ch); o.setsampwidth(2); o.setframerate(fr)
o.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes()); o.close()
print(f'{dst}: {len(a) / fr:.2f} s, {ch} ch, {fr} Hz (from {n / fr:.2f} s, {sw * 8}-bit)')
