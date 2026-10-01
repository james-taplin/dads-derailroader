using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// Modelled oiling nubs at a main-rod end (James, 2026-10-01: "pick any of the nubs at each point, whichever has the best clearance, for
// gameplay reasons"). Railroader's modellers put small nubs (round caps, posts, hex heads) on top of the running gear at the pins and
// rod ends; the oil-cup map of all 21 stock locos measured them. Around the crank end of a main rod (in the rod's own level pose, the
// gear at that phase) the top surface of the moving parts is sampled with rays on a 1 cm grid; a bump is a cell at least 6 mm above
// the median of its surroundings and the highest within 2 cm. Every bump on a travelling part is a candidate; the one whose cup space
// stays clear to the widest radius through the whole turn wins (ties: the higher bump, then the nearer to the rod end).
// Standalone on purpose: it takes the raycast, the clearance test and the spacing test as delegates, so the type-check test compiles it.
public static class Rr2dvOilNubs
{
    public delegate bool RayFn(Vector3 origin, Vector3 direction, float distance, out RaycastHit hit);
    // clearance of a cup at `pos` riding `host`, for a cup space of radius `radius`: null when clear, else what is in the way
    public delegate string ClearFn(Vector3 pos, Transform host, float radius);

    public sealed class Candidate
    {
        public Vector3 world, pivot, local;   // the peak, the cup's pivot above it, the pivot in the host's own space (at the scan pose)
        public Transform host;
        public float rise, margin, distance;
    }

    public const float Step = .01f, MinRise = .006f, MinNormalY = .8f;
    static readonly float[] Radii = { .035f, .045f, .055f, .065f, .08f };

    // Candidates around `end`, best first. `lift` = how far the cup's pivot sits above the surface it stands on.
    public static List<Candidate> Find(RayFn ray, Vector3 end, float reach, float lift, Func<Transform, bool> usable,
                                       ClearFn clear, Func<Vector3, bool> spaced, out string summary)
    {
        int half = Mathf.RoundToInt(reach / Step);
        int n = 2 * half + 1;
        var h = new float[n, n]; var ok = new bool[n, n]; var level = new bool[n, n]; var host = new Transform[n, n];
        for (int ix = 0; ix < n; ix++)
            for (int iz = 0; iz < n; iz++)
            {
                float dx = (ix - half) * Step, dz = (iz - half) * Step;
                if (dx * dx + dz * dz > reach * reach) continue;
                RaycastHit hit;
                if (!ray(new Vector3(end.x + dx, end.y + .3f, end.z + dz), Vector3.down, .7f, out hit)) continue;
                h[ix, iz] = hit.point.y; ok[ix, iz] = true; level[ix, iz] = hit.normal.y >= MinNormalY;
                host[ix, iz] = hit.collider.transform.parent;
            }
        int win = 5, peakWin = 2;
        var rise = new float[n, n];
        var buf = new List<float>();
        for (int ix = 0; ix < n; ix++)
            for (int iz = 0; iz < n; iz++)
            {
                if (!ok[ix, iz]) continue;
                buf.Clear();
                for (int dx = -win; dx <= win; dx++)
                    for (int dz = -win; dz <= win; dz++)
                    { int x = ix + dx, z = iz + dz; if (x >= 0 && z >= 0 && x < n && z < n && ok[x, z]) buf.Add(h[x, z]); }
                buf.Sort();
                rise[ix, iz] = h[ix, iz] - buf[buf.Count / 2];
            }
        var found = new List<Candidate>();
        int peaks = 0, notUsable = 0, notLevel = 0, crowded = 0, blocked = 0;
        for (int ix = 0; ix < n; ix++)
            for (int iz = 0; iz < n; iz++)
            {
                if (!ok[ix, iz] || rise[ix, iz] < MinRise) continue;
                bool peak = true;
                for (int dx = -peakWin; dx <= peakWin && peak; dx++)
                    for (int dz = -peakWin; dz <= peakWin; dz++)
                    { int x = ix + dx, z = iz + dz; if (x >= 0 && z >= 0 && x < n && z < n && ok[x, z] && (h[x, z] > h[ix, iz] || (h[x, z] == h[ix, iz] && (x < ix || (x == ix && z < iz))))) { peak = false; break; } }
                if (!peak) continue;
                peaks++;
                var hostT = host[ix, iz];
                if (!hostT || !usable(hostT)) { notUsable++; continue; }
                if (!level[ix, iz]) { notLevel++; continue; }
                var world = new Vector3(end.x + (ix - half) * Step, h[ix, iz], end.z + (iz - half) * Step);
                var pivot = world + Vector3.up * lift;
                if (!spaced(pivot)) { crowded++; continue; }
                float margin = 0;
                foreach (float r in Radii)
                {
                    if (clear(pivot, hostT, r) != null) break;
                    margin = r;
                }
                if (margin < Radii[0]) { blocked++; continue; }
                found.Add(new Candidate
                {
                    world = world, pivot = pivot, local = hostT.InverseTransformPoint(pivot), host = hostT, rise = rise[ix, iz], margin = margin,
                    distance = Vector2.Distance(new Vector2(world.x, world.z), new Vector2(end.x, end.z))
                });
            }
        summary = $"{peaks} bump(s) within {reach:F2} m of the end: {notUsable} not on a travelling part, {notLevel} not level, {crowded} too close to another cup, " +
                  $"{blocked} without clear space, {found.Count} usable";
        return found.OrderByDescending(c => c.margin).ThenByDescending(c => c.rise).ThenBy(c => c.distance).ToList();
    }
}
