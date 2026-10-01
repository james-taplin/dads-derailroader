using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Oil-cup candidate map for the stock locomotives. Unity editor only.
// Read-only like VfMeasure: temporary copies in an empty scene, temporary colliders removed again, nothing saved.
// Input: Assets/Rr2dv/ProbeInput.json (the probe's own input). Output: <VF_OUT>/vf-oil.json and result.json.
// It applies the oil-cup requirements of Rr2dvPlacement.SeatRr2dvOilCups to the SOURCE prefab of each loco, but records
// every candidate and the reason each one passed or failed, instead of only the cups that were placed:
//   * main rods found by how they move (one end on a line, the other on a circle), per side and cylinder;
//   * for each end of each main rod: the seat scan in the rod's own level pose (4 x 3 cm level footprint within 0.3 m of
//     the end, highest first), the cup-space clearance through a whole turn, and the 12 cm spacing rule;
//   * running-board seats per driving axle and side, with a count of why the cells failed.
// Nothing here decides a conversion value: the offline analysis turns the result into defined positions for the loco table.
// Coordinates: car space = the instantiated prefab at the origin; x right, y up, z front.
public static class VfOil
{
    [Serializable] public class MapEntry { public string key, asset, guid; }
    [Serializable] public class Wheelset { public string clip, clipAsset; public float diameter, offset, length; public int axles; }
    [Serializable] public class Vehicle { public string id, role, prefab; public Wheelset[] wheelsets; public MapEntry[] animationMap; }
    [Serializable] public class Input { public int schema; public Vehicle[] vehicles; }

    [Serializable] public class Part { public string path; public float travel, turn; public bool lowerLod; }
    [Serializable] public class RodOut
    {
        public string path, verdict, reason; public int side; public float extent, crankThrow, crossZ, levelPhase;
        public float[] endA, endB; public float rangeAy, rangeAz, rangeBy, rangeBz; public string crankEnd;
    }
    [Serializable] public class Cell { public float t, u, y; public bool level, footprint; }
    [Serializable] public class EndSeat
    {
        public string rod, end; public bool found; public string why; public float[] world, local; public float levelPhase;
        public int cellsTested, cellsLevel, cellsFootprint; public Cell[] cells; public bool spaced, clear; public string clash;
    }
    [Serializable] public class PairOut { public string left, right; public float crossZ; public bool crankEndBoth, crossEndBoth; }
    [Serializable] public class BoardSeat
    {
        public float axleZ; public int side; public bool found; public string seat; public float[] world;
        public int cells, notLevel, noFootprint, overhead, sideWall, crowded, unclear;
    }
    [Serializable] public class AxleOut { public string clip; public string path; public float z, x; }
    [Serializable] public class VehicleOut
    {
        public string id, role, prefab; public float wheelRadius; public bool skipped; public string note;
        public int renderers, lowerLodRenderers;
        public Part[] movingParts; public RodOut[] rods; public EndSeat[] endSeats; public PairOut[] pairs;
        public AxleOut[] axles; public BoardSeat[] boardSeats; public string[] log;
    }
    [Serializable] public class Spec
    {
        public float cupPivotAboveBase = CupPivotAboveBase, cupSeatSink = CupSeatSink, clearRadius = CupClearRadius, clearHeight = CupClearHeight,
            spacing = CupSpacing, footprintAlong = 0.04f, footprintAcross = 0.03f, seatReach = 0.3f; public int maxPairs = 6;
    }
    [Serializable] public class Output { public int schema = 1; public string unity; public Spec spec = new Spec(); public VehicleOut[] vehicles; public string[] problems; }
    [Serializable] public class Result { public string status; public int exitCode, problems; public string error; }

    const string InputAsset = "Assets/Rr2dv/ProbeInput.json";
    const float CupPivotAboveBase = 0.0175f, CupSeatSink = 0.003f, CupClearRadius = .035f, CupClearHeight = .09f, CupSpacing = .12f;
    const int Phases = 16;
    static readonly List<string> Problems = new List<string>();
    static List<string> Log = new List<string>();

    public static void Run()
    {
        int exit = 0;
        string output = Environment.GetEnvironmentVariable("VF_OUT");
        var result = new Result { status = "failed", exitCode = 1 };
        try
        {
            if (string.IsNullOrEmpty(output)) throw new InvalidOperationException("VF_OUT is required");
            Directory.CreateDirectory(output);
            Problems.Clear();
            var project = Directory.GetParent(Application.dataPath).FullName;
            var input = JsonUtility.FromJson<Input>(File.ReadAllText(Path.Combine(project, InputAsset)));
            if (input == null || input.schema != 1 || input.vehicles == null) throw new InvalidDataException("unsupported probe input");
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var outp = new Output { unity = Application.unityVersion, vehicles = input.vehicles.Select(Measure).ToArray() };
            outp.problems = Problems.ToArray();
            File.WriteAllText(Path.Combine(output, "vf-oil.json"), JsonUtility.ToJson(outp, true));
            exit = Problems.Count > 0 ? 2 : 0;
            result = new Result { status = exit == 0 ? "passed" : "problems", exitCode = exit, problems = Problems.Count };
        }
        catch (Exception e)
        {
            Debug.LogException(e);
            exit = 1;
            result = new Result { status = "failed", exitCode = 1, problems = Problems.Count, error = e.ToString() };
        }
        finally
        {
            if (!string.IsNullOrEmpty(output) && Directory.Exists(output))
                File.WriteAllText(Path.Combine(output, "result.json"), JsonUtility.ToJson(result, true));
            EditorApplication.Exit(exit);
        }
    }

    // ------------------------------------------------------------------------------------------------------------------
    sealed class MainRod { public Transform rod; public Vector3 crankEnd, crossEnd; public float side, throwM, crossZ, levelPhase; }

    static VehicleOut Measure(Vehicle v)
    {
        var o = new VehicleOut { id = v.id, role = v.role, prefab = v.prefab, log = new string[0] };
        if (v.role != "locomotive") { o.skipped = true; o.note = "not a locomotive body: no oil cups"; return o; }
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(v.prefab);
        if (!prefab) { Problems.Add(v.id + ": prefab not found " + v.prefab); return o; }
        Log = new List<string>();
        var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        var lowerOff = new List<Renderer>();
        try
        {
            var root = go.transform;
            var clips = (v.wheelsets ?? new Wheelset[0]).Select(w => string.IsNullOrEmpty(w.clipAsset) ? null : AssetDatabase.LoadAssetAtPath<AnimationClip>(w.clipAsset)).Where(c => c).ToArray();
            // the wheelset with the most axles is the drivers (C-40 also has a 'Lubricator' clip with a 5.7 m 'wheel')
            o.wheelRadius = (v.wheelsets ?? new Wheelset[0]).OrderByDescending(w => w.axles).Select(w => w.diameter / 2f).DefaultIfEmpty(0f).First();
            var lower = LowerLod(root);
            o.lowerLodRenderers = lower.Count;
            foreach (var r in lower) if (r.enabled) { r.enabled = false; lowerOff.Add(r); }   // LOD0 only, as the build does
            o.renderers = root.GetComponentsInChildren<Renderer>(true).Count(r => r.enabled && r.gameObject.activeInHierarchy);
            o.axles = Axles(v, root);
            Sample(go, clips, 0f);
            o.movingParts = MovingParts(go, clips, lower);
            var rods = new List<RodOut>();
            var main = MainRods(go, root, clips, lower, rods);
            o.rods = rods.ToArray();
            var seats = new List<EndSeat>();
            using (var hits = new Hits(root))
            {
                foreach (var m in main)
                {
                    seats.Add(EndSeatScan(hits, go, root, clips, m, true));
                    seats.Add(EndSeatScan(hits, go, root, clips, m, false));
                }
                o.boardSeats = Boards(hits, root, o);
            }
            o.endSeats = seats.ToArray();
            o.pairs = Pairs(root, main, seats);
            o.log = Log.ToArray();
        }
        catch (Exception e) { Problems.Add(v.id + ": " + e.GetType().Name + ": " + e.Message); o.note = e.ToString(); }
        finally
        {
            foreach (var r in lowerOff) if (r) r.enabled = true;
            Object.DestroyImmediate(go);
        }
        return o;
    }

    // ---- driving gear -----------------------------------------------------------------------------------------------
    static void Sample(GameObject go, AnimationClip[] clips, float phase)
    {
        foreach (var c in clips) c.SampleAnimation(go, phase * c.length);
        Physics.SyncTransforms();
    }

    static HashSet<Renderer> LowerLod(Transform root)
    {
        var lower = new HashSet<Renderer>();
        var top = new HashSet<Renderer>();
        foreach (var group in root.GetComponentsInChildren<LODGroup>(true))
        {
            var levels = group.GetLODs();
            for (int i = 0; i < levels.Length; i++)
                foreach (var r in levels[i].renderers) if (r) { if (i == 0) top.Add(r); else lower.Add(r); }
        }
        foreach (var r in root.GetComponentsInChildren<Renderer>(true))
            if (System.Text.RegularExpressions.Regex.IsMatch(r.gameObject.name, @"(?i)lod[1-9]\d*$")) lower.Add(r);
        lower.ExceptWith(top);
        return lower;
    }

    static Part[] MovingParts(GameObject go, AnimationClip[] clips, HashSet<Renderer> lower)
    {
        var rs = go.GetComponentsInChildren<MeshRenderer>(true).Where(r => r.enabled && r.gameObject.activeInHierarchy).ToArray();
        var samples = rs.ToDictionary(r => r, r => new List<KeyValuePair<Vector3, Quaternion>>());
        foreach (var phase in new[] { 0f, .25f, .5f, .75f })
        {
            Sample(go, clips, phase);
            foreach (var r in rs) samples[r].Add(new KeyValuePair<Vector3, Quaternion>(r.bounds.center, r.transform.rotation));
        }
        Sample(go, clips, 0f);
        var list = new List<Part>();
        foreach (var kv in samples)
        {
            float travel = 0f, turn = 0f;
            foreach (var a in kv.Value) foreach (var b in kv.Value)
            {
                travel = Mathf.Max(travel, Vector3.Distance(a.Key, b.Key));
                turn = Mathf.Max(turn, Quaternion.Angle(a.Value, b.Value));
            }
            if (travel > .02f || turn > 5f)
                list.Add(new Part { path = AnimationUtility.CalculateTransformPath(kv.Key.transform, go.transform), travel = travel, turn = turn, lowerLod = lower.Contains(kv.Key) });
        }
        return list.OrderBy(p => p.path, StringComparer.Ordinal).ToArray();
    }

    sealed class Axes { public Vector3[] axes; public float[] ext; }

    static Axes Principal(Vector3[] pts, Vector3 c)
    {
        float xx = 0, xy = 0, xz = 0, yy = 0, yz = 0, zz = 0;
        foreach (var p in pts) { var d = p - c; xx += d.x * d.x; xy += d.x * d.y; xz += d.x * d.z; yy += d.y * d.y; yz += d.y * d.z; zz += d.z * d.z; }
        Func<Vector3, Vector3> Mul = v => new Vector3(xx * v.x + xy * v.y + xz * v.z, xy * v.x + yy * v.y + yz * v.z, xz * v.x + yz * v.y + zz * v.z);
        Func<Vector3, Func<Vector3, Vector3>, Vector3> Dominant = (start, project) =>
        {
            var v = project(start).normalized;
            for (int i = 0; i < 64; i++) { var n = project(Mul(v)); if (n.sqrMagnitude < 1e-12f) break; v = n.normalized; }
            return v;
        };
        var a0 = Dominant(new Vector3(.3f, .2f, .9f), v => v);
        var a1 = Dominant(Vector3.Cross(a0, Math.Abs(a0.y) < .9f ? Vector3.up : Vector3.right), v => v - Vector3.Dot(v, a0) * a0);
        var a2 = Vector3.Cross(a0, a1).normalized;
        var axes = new[] { a0, a1, a2 };
        var ext = axes.Select(a => pts.Max(p => Vector3.Dot(p - c, a)) - pts.Min(p => Vector3.Dot(p - c, a))).ToArray();
        return new Axes { axes = axes, ext = ext };
    }

    // A main rod by how it moves: one end on a straight line (crosshead), the other on a circle (crank pin). Every long
    // moving part is recorded with its verdict so the offline analysis sees what was rejected and why.
    static List<MainRod> MainRods(GameObject go, Transform root, AnimationClip[] clips, HashSet<Renderer> lower, List<RodOut> report)
    {
        var found = new List<MainRod>();
        var seen = new Dictionary<MainRod, RodOut>();
        try
        {
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                var mr = mf.GetComponent<MeshRenderer>();
                if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0 || !mr || !mr.enabled || !mf.gameObject.activeInHierarchy || lower.Contains(mr)) continue;
                var vs = mf.sharedMesh.vertices;
                var c = vs.Aggregate(Vector3.zero, (a, b) => a + b) / vs.Length;
                var principal = Principal(vs, c);
                var axes = principal.axes; var ext = principal.ext;
                if (ext[0] < .5f) continue;
                var e0 = c + axes[0] * vs.Min(p => Vector3.Dot(p - c, axes[0]));
                var e1 = c + axes[0] * vs.Max(p => Vector3.Dot(p - c, axes[0]));
                var p0 = new Vector3[Phases]; var p1 = new Vector3[Phases]; var tilt = new float[Phases];
                Sample(go, clips, 0f);
                var rest0 = mf.transform.TransformPoint(e0); var rest1 = mf.transform.TransformPoint(e1);
                for (int k = 0; k < Phases; k++)
                {
                    Sample(go, clips, k / (float)Phases);
                    p0[k] = mf.transform.TransformPoint(e0); p1[k] = mf.transform.TransformPoint(e1);
                    tilt[k] = Mathf.Abs((p1[k] - p0[k]).normalized.y);
                }
                Func<Vector3[], float> Ry = p => p.Max(q => q.y) - p.Min(q => q.y);
                Func<Vector3[], float> Rz = p => p.Max(q => q.z) - p.Min(q => q.z);
                Func<Vector3[], bool> Circle = p => Ry(p) > .1f && Rz(p) > .1f;
                Func<Vector3[], bool> Line = p => Ry(p) < .045f && Rz(p) > .1f;   // as Rr2dvPlacement: F-71 and C-55 wander 3.7 cm
                if (Ry(p0) < .01f && Rz(p0) < .01f && Ry(p1) < .01f && Rz(p1) < .01f) continue;   // does not move: not running gear
                var rep = new RodOut
                {
                    path = AnimationUtility.CalculateTransformPath(mf.transform, root), extent = ext[0],
                    side = (int)Mathf.Sign(mf.transform.TransformPoint(c).x),
                    endA = V(rest0), endB = V(rest1), rangeAy = Ry(p0), rangeAz = Rz(p0), rangeBy = Ry(p1), rangeBz = Rz(p1)
                };
                var wx = vs.Select(q => mf.transform.TransformPoint(q).x).ToArray();
                bool crank0 = Circle(p0) && Line(p1), crank1 = Circle(p1) && Line(p0);
                if (ext[0] < .8f) { rep.verdict = "rejected"; rep.reason = "shorter than 0.8 m: a crank throw or a crosshead"; }
                else if (wx.Max() - wx.Min() > .4f || Mathf.Abs(wx.Average()) < .3f) { rep.verdict = "rejected"; rep.reason = "not a single side's rod outside the frames"; }
                else if (!crank0 && !crank1)
                {
                    bool two = Circle(p0) && Circle(p1);
                    rep.verdict = "rejected"; rep.reason = two ? "both ends circle: a coupling rod" : "no end runs on a line and the other on a circle";
                }
                else if (Ry(crank0 ? p0 : p1) / 2 < .2f) { rep.verdict = "rejected"; rep.reason = "crank throw under 0.2 m: an eccentric or valve-gear rod"; }
                else
                {
                    var cross = crank0 ? p1 : p0;
                    int level = Enumerable.Range(0, Phases).OrderBy(k => tilt[k]).First();
                    var m = new MainRod
                    {
                        rod = mf.transform, crankEnd = crank0 ? e0 : e1, crossEnd = crank0 ? e1 : e0, side = rep.side,
                        throwM = Ry(crank0 ? p0 : p1) / 2, crossZ = cross.Average(q => q.z), levelPhase = level / (float)Phases
                    };
                    rep.verdict = "candidate"; rep.crankThrow = m.throwM; rep.crossZ = m.crossZ; rep.levelPhase = m.levelPhase;
                    rep.crankEnd = crank0 ? "A" : "B";
                    found.Add(m); seen[m] = rep;
                }
                report.Add(rep);
            }
        }
        finally { Sample(go, clips, 0f); }
        // one per side and cylinder (crosshead within 0.5 m): the biggest circle is the crank, a smaller one an eccentric
        var kept = found.GroupBy(m => new { m.side, bin = Mathf.Round(m.crossZ / .5f) }).Select(g => g.OrderByDescending(m => m.throwM).First()).ToList();
        foreach (var m in found) { seen[m].verdict = kept.Contains(m) ? "main rod" : "rejected"; if (!kept.Contains(m)) seen[m].reason = "a smaller circle beside a main rod (eccentric or valve gear)"; }
        return kept;
    }

    static List<MainRod[]> PairRods(List<MainRod> rods)
    {
        var pairs = new List<MainRod[]>();
        var right = rods.Where(m => m.side > 0).ToList();
        foreach (var l in rods.Where(m => m.side < 0).OrderByDescending(m => m.crossZ))
        {
            var r = right.OrderBy(m => Mathf.Abs(m.crossZ - l.crossZ)).FirstOrDefault();
            if (r == null || Mathf.Abs(r.crossZ - l.crossZ) > .3f) { Log.Add($"main rod {l.rod.name}: no right-hand partner"); continue; }
            right.Remove(r);
            pairs.Add(new[] { l, r });
        }
        foreach (var r in right) Log.Add($"main rod {r.rod.name}: no left-hand partner");
        return pairs;
    }

    // ---- seats on a rod end -----------------------------------------------------------------------------------------
    static EndSeat EndSeatScan(Hits hits, GameObject go, Transform root, AnimationClip[] clips, MainRod m, bool crankEnd)
    {
        var s = new EndSeat { rod = AnimationUtility.CalculateTransformPath(m.rod, root), end = crankEnd ? "crank" : "cross", levelPhase = m.levelPhase };
        var cells = new List<Cell>();
        Vector3 local = Vector3.zero; bool ok = false;
        try
        {
            Sample(go, clips, m.levelPhase);
            var e = m.rod.TransformPoint(crankEnd ? m.crankEnd : m.crossEnd);
            var o = m.rod.TransformPoint(crankEnd ? m.crossEnd : m.crankEnd);
            var inward = new Vector3(o.x - e.x, 0, o.z - e.z).normalized;
            var across = Vector3.Cross(Vector3.up, inward).normalized;
            float best = float.MinValue;
            for (float t = 0; t <= .3001f; t += .02f)
                for (float u = -.06f; u <= .0601f; u += .02f)
                {
                    var origin = e + inward * t + across * u + Vector3.up * .5f;
                    var cell = new Cell { t = t, u = u };
                    s.cellsTested++;
                    if (hits.Ray(origin, Vector3.down, 1f, out var hit, m.rod))
                    {
                        cell.y = hit.point.y; cell.level = hit.normal.y >= .9f;
                        if (cell.level)
                        {
                            s.cellsLevel++;
                            bool footprint = true;
                            foreach (var d in new[] { inward * .02f, -inward * .02f, across * .015f, -across * .015f })
                                if (!hits.Ray(origin + d, Vector3.down, 1f, out var edge, m.rod) || edge.normal.y < .9f || Mathf.Abs(edge.point.y - hit.point.y) > .006f)
                                    footprint = false;
                            cell.footprint = footprint;
                            if (footprint)
                            {
                                s.cellsFootprint++;
                                if (hit.point.y > best)
                                {
                                    best = hit.point.y;
                                    local = m.rod.InverseTransformPoint(hit.point + Vector3.up * (CupPivotAboveBase - CupSeatSink));
                                    ok = true;
                                }
                            }
                        }
                    }
                    cells.Add(cell);
                }
        }
        finally { Sample(go, clips, 0f); }
        s.cells = cells.ToArray();
        if (!ok) { s.why = "no level spot on the rod within 0.3 m of the end"; return s; }
        var pos = m.rod.TransformPoint(local);
        s.world = V(pos); s.local = V(local);
        s.spaced = true;   // spacing between cups is judged offline across the pair list (12 cm)
        s.clear = Clear(hits, go, clips, pos, m.rod, out var clash);
        s.clash = clash;
        s.found = s.clear;
        if (!s.clear) s.why = "something visible in the cup's space: " + clash;
        return s;
    }

    // The cup's own space (3.5 cm radius, 9 cm tall above its base) checked at eight phases of the drivers' turn.
    static bool Clear(Hits hits, GameObject go, AnimationClip[] clips, Vector3 pos, Transform rider, out string why)
    {
        why = null;
        var local = rider ? rider.InverseTransformPoint(pos) : pos;
        try
        {
            foreach (var phase in new[] { 0f, .125f, .25f, .375f, .5f, .625f, .75f, .875f })
            {
                Sample(go, clips, phase);
                var p = rider ? rider.TransformPoint(local) : pos;
                var centre = new Vector3(p.x, p.y - CupPivotAboveBase + CupSeatSink, p.z);
                var rim = new[] { Vector3.zero, new Vector3(CupClearRadius, 0, 0), new Vector3(-CupClearRadius, 0, 0), new Vector3(0, 0, CupClearRadius), new Vector3(0, 0, -CupClearRadius) };
                foreach (var o in rim)
                    if (hits.Ray(centre + o + Vector3.up * .006f, Vector3.up, CupClearHeight, out var h, null)) { why = $"{h.collider.transform.parent.name} above it at phase {phase:F2}"; return false; }
                foreach (var o in rim)
                    if (hits.Ray(centre + o + Vector3.up * (CupClearHeight + .04f), Vector3.down, CupClearHeight + .04f - .006f, out var h, null)) { why = $"{h.collider.transform.parent.name} over it at phase {phase:F2}"; return false; }
                foreach (float y in new[] { .02f, .045f, .075f })
                    foreach (var d in new[] { Vector3.right, Vector3.left, Vector3.forward, Vector3.back })
                        if (hits.Ray(centre + Vector3.up * y + d * 3 * CupClearRadius, -d, 4 * CupClearRadius, out var h, null) &&
                            Vector3.Distance(new Vector3(h.point.x, 0, h.point.z), new Vector3(centre.x, 0, centre.z)) <= CupClearRadius)
                        { why = $"{h.collider.transform.parent.name} inside it at phase {phase:F2}"; return false; }
            }
            return true;
        }
        finally { Sample(go, clips, 0f); }
    }

    static PairOut[] Pairs(Transform root, List<MainRod> rods, List<EndSeat> seats)
    {
        Func<MainRod, string, EndSeat> Of = (m, end) => seats.FirstOrDefault(s => s.rod == AnimationUtility.CalculateTransformPath(m.rod, root) && s.end == end && s.found);
        return PairRods(rods).Select(p => new PairOut
        {
            left = p[0].rod.name, right = p[1].rod.name, crossZ = (p[0].crossZ + p[1].crossZ) / 2f,
            crankEndBoth = Of(p[0], "crank") != null && Of(p[1], "crank") != null,
            crossEndBoth = Of(p[0], "cross") != null && Of(p[1], "cross") != null
        }).ToArray();
    }

    // ---- running boards ---------------------------------------------------------------------------------------------
    static AxleOut[] Axles(Vehicle v, Transform root)
    {
        var list = new List<AxleOut>();
        foreach (var w in v.wheelsets ?? new Wheelset[0])
        {
            var clip = string.IsNullOrEmpty(w.clipAsset) ? null : AssetDatabase.LoadAssetAtPath<AnimationClip>(w.clipAsset);
            if (!clip) continue;
            foreach (var path in AnimationUtility.GetCurveBindings(clip)
                         .Where(b => b.propertyName.IndexOf("Rotation", StringComparison.OrdinalIgnoreCase) >= 0 || b.propertyName.IndexOf("Euler", StringComparison.OrdinalIgnoreCase) >= 0)
                         .Select(b => b.path).Distinct().OrderBy(p => p, StringComparer.Ordinal))
            {
                var t = string.IsNullOrEmpty(path) ? root : root.Find(path);
                if (!t) continue;
                var radius = w.diameter / 2f;
                // a wheel node: some mesh under it reaches about the wheel radius from its pivot
                bool wheel = t.GetComponentsInChildren<MeshFilter>(true).Any(f => f.sharedMesh && f.sharedMesh.vertices.Any(q =>
                { var d = f.transform.TransformPoint(q) - t.position; return Mathf.Abs(new Vector2(d.y, d.z).magnitude - radius) < .15f * radius; }));
                if (wheel) list.Add(new AxleOut { clip = w.clip, path = path, z = t.position.z, x = t.position.x });
            }
        }
        return list.ToArray();
    }

    static BoardSeat[] Boards(Hits hits, Transform root, VehicleOut o)
    {
        var result = new List<BoardSeat>();
        float wheelRadius = o.wheelRadius;
        var zs = o.axles.Where(a => a.clip != null).Select(a => Mathf.Round(a.z * 1000f) / 1000f).Distinct().OrderBy(z => z).ToArray();
        var moving = new HashSet<string>(o.movingParts.Where(p => p.travel > .02f).Select(p => p.path));
        foreach (float zHint in zs)
            foreach (float side in new[] { -1f, 1f })
            {
                var b = new BoardSeat { axleZ = zHint, side = (int)side };
                Vector3 pos = Vector3.zero; string seat = null;
                for (float x = 1.65f; x >= .8f && !b.found; x -= .025f)
                    for (int dz = 0; dz < 9 && !b.found; dz++)
                    {
                        float z = zHint + (dz == 0 ? 0 : (dz % 2 == 0 ? -1 : 1) * ((dz + 1) / 2) * .05f);
                        var origin = new Vector3(side * x, 2 * wheelRadius + 1.2f, z);
                        b.cells++;
                        if (!hits.Ray(origin, Vector3.down, 1.8f, out var hit, null) || hit.normal.y < .97f || hit.point.y < 2 * wheelRadius + .08f) { b.notLevel++; continue; }
                        if (moving.Contains(AnimationUtility.CalculateTransformPath(hit.collider.transform.parent, root))) { b.notLevel++; continue; }   // a rod cannot be a board
                        bool footprint = true;
                        foreach (var offset in new[] { new Vector3(.045f, 0, 0), new Vector3(-.045f, 0, 0), new Vector3(0, 0, .045f), new Vector3(0, 0, -.045f) })
                            if (!hits.Ray(origin + offset, Vector3.down, 1.8f, out var edge, null) || edge.normal.y < .97f || Mathf.Abs(edge.point.y - hit.point.y) > .01f) footprint = false;
                        if (!footprint) { b.noFootprint++; continue; }
                        var p = hit.point + Vector3.up * (CupPivotAboveBase - CupSeatSink);
                        if (hits.Ray(p + Vector3.up * .08f, Vector3.up, .12f, out var overhead, null)) { b.overhead++; continue; }
                        if (hits.Ray(p + Vector3.up * .08f, Vector3.right * side, .6f, out var sideHit, null)) { b.sideWall++; continue; }
                        if (result.Any(r => r.found && r.world != null && Vector3.Distance(new Vector3(r.world[0], r.world[1], r.world[2]), p) < CupSpacing)) { b.crowded++; continue; }
                        b.found = true; pos = p; seat = "running board on " + hit.collider.transform.parent.name;
                    }
                b.seat = seat; b.world = b.found ? V(pos) : null;
                result.Add(b);
            }
        return result.ToArray();
    }

    // Temporary MeshColliders on every visible mesh under the root (their own colliders switched off) for many raycasts.
    sealed class Hits : IDisposable
    {
        readonly List<GameObject> temp = new List<GameObject>();
        readonly List<Collider> off = new List<Collider>();
        readonly RaycastHit[] buf = new RaycastHit[256];
        PhysicsScene scene;
        public Hits(Transform root)
        {
            scene = root.gameObject.scene.GetPhysicsScene();
            foreach (var c in root.GetComponentsInChildren<Collider>(true)) if (c.enabled) { c.enabled = false; off.Add(c); }
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(false))
            {
                var r = mf.GetComponent<MeshRenderer>();
                if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0 || !r || !r.enabled) continue;
                var g = new GameObject("[vis]"); g.transform.SetParent(mf.transform, false);
                g.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
                temp.Add(g);
            }
            Physics.SyncTransforms();
        }
        public bool Ray(Vector3 o, Vector3 d, float dist, out RaycastHit hit, Transform only)
        {
            int n = scene.Raycast(o, d.normalized, buf, dist, ~0, QueryTriggerInteraction.Ignore);
            hit = default(RaycastHit); bool found = false;
            for (int i = 0; i < n; i++)
            {
                var c = buf[i].collider;
                if (c.name != "[vis]" || (only && !c.transform.IsChildOf(only))) continue;
                if (!found || buf[i].distance < hit.distance) { hit = buf[i]; found = true; }
            }
            return found;
        }
        public void Dispose() { foreach (var g in temp) if (g) Object.DestroyImmediate(g); foreach (var c in off) if (c) c.enabled = true; }
    }

    static float[] V(Vector3 v) => new[] { v.x, v.y, v.z };
}
