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
    // Modelled oiling nubs (Railroader's own, on top of the running gear): small islands of the part's mesh, and small raised
    // bumps found by sampling the part's top surface with rays (so a nub welded into the rod's own mesh is found too).
    [Serializable] public class Island
    {
        public int triangles; public float[] size, centre, top, local; public float topArea; public bool largest;
        public float alongFromEndA, alongFromEndB;
    }
    [Serializable] public class Bump
    {
        public float[] world, local, size; public float rise, plateauArea, peakY, alongFromEndA, alongFromEndB; public int cells;
        public bool clear; public string clash;
    }
    [Serializable] public class NubPart
    {
        public string path, motion, note; public float phase, extent, step; public int gridCells, meshIslands;
        public float[] endA, endB; public Island[] islands; public Bump[] bumps;
    }
    [Serializable] public class AxleOut { public string clip; public string path; public float z, x; }
    [Serializable] public class VehicleOut
    {
        public string id, role, prefab; public float wheelRadius; public bool skipped; public string note;
        public int renderers, lowerLodRenderers;
        public Part[] movingParts; public RodOut[] rods; public EndSeat[] endSeats; public PairOut[] pairs;
        public AxleOut[] axles; public BoardSeat[] boardSeats; public NubPart[] nubParts; public string[] renders; public string[] log;
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
    static string OutDir = "";

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
            OutDir = output;
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
                o.nubParts = NubParts(hits, go, root, clips, lower, o);
            }
            o.endSeats = seats.ToArray();
            o.renders = RenderNubs(go, root, clips, o);
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


    // ---- modelled nubs ----------------------------------------------------------------------------------------------
    const float NubGrid = 0.01f, NubMinRise = 0.004f, NubSeedRise = 0.006f;

    static NubPart[] NubParts(Hits hits, GameObject go, Transform root, AnimationClip[] clips, HashSet<Renderer> lower, VehicleOut o)
    {
        var result = new List<NubPart>();
        var motion = o.movingParts.ToDictionary(p => p.path, p => p);
        float runningGearTop = 2 * o.wheelRadius + .6f;
        Sample(go, clips, 0f);
        foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
        {
            var mr = mf.GetComponent<MeshRenderer>();
            if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0 || !mr || !mr.enabled || !mf.gameObject.activeInHierarchy || lower.Contains(mr)) continue;
            var b = mr.bounds;
            float longest = Mathf.Max(b.max.z - b.min.z, Mathf.Max(b.max.y - b.min.y, b.max.x - b.min.x));
            if (longest > 7f || longest < .1f) continue;
            string path = AnimationUtility.CalculateTransformPath(mf.transform, root);
            Part mp; bool moving = motion.TryGetValue(path, out mp);
            bool travels = moving && mp.travel > .02f;
            if (moving && !travels) continue;                              // a wheel, axle or crank turning in place: not a nub host
            bool big = !moving && longest > 2.5f;
            if (big && b.min.y > 2 * o.wheelRadius) continue;   // a big static part is scanned only when it reaches down to the axleboxes (frames), in windows round each axle
            if (big)
            {
                foreach (var w in AxleWindows(hits, mf, o, path)) result.Add(w);
                continue;
            }
            if (!moving && (b.center.y > runningGearTop || Mathf.Abs(b.center.x) < .3f)) continue;   // static running gear only, outside the frames
            if (travels && Mathf.Abs(b.center.x) < .3f) continue;
            var part = new NubPart { path = path, motion = travels ? "travels" : "static" };
            var vs = mf.sharedMesh.vertices;
            var c = vs.Aggregate(Vector3.zero, (a, q) => a + q) / vs.Length;
            var principal = Principal(vs, c);
            var ea = c + principal.axes[0] * vs.Min(q => Vector3.Dot(q - c, principal.axes[0]));
            var eb = c + principal.axes[0] * vs.Max(q => Vector3.Dot(q - c, principal.axes[0]));
            part.extent = principal.ext[0];
            // the pose to scan: the part's flattest (a travelling rod in its own level pose); rest for the static
            float phase = 0f;
            if (travels)
            {
                float best = float.MaxValue;
                for (int k = 0; k < Phases; k++)
                {
                    Sample(go, clips, k / (float)Phases);
                    float tilt = Mathf.Abs((mf.transform.TransformPoint(eb) - mf.transform.TransformPoint(ea)).normalized.y);
                    if (tilt < best) { best = tilt; phase = k / (float)Phases; }
                }
            }
            part.phase = phase;
            try
            {
                Sample(go, clips, phase);
                part.endA = V(mf.transform.TransformPoint(ea)); part.endB = V(mf.transform.TransformPoint(eb));
                part.islands = Islands(mf, ea, eb);
                part.meshIslands = part.islands.Length;
                part.islands = part.islands.Where(i => !i.largest).Take(12).ToArray();
                part.bumps = Bumps(hits, go, clips, mf, ea, eb, part, travels);
            }
            finally { Sample(go, clips, 0f); }
            if (part.islands.Length > 0 || part.bumps.Length > 0) result.Add(part);
        }
        return result.ToArray();
    }


    // The axleboxes are usually part of the frame mesh, which is far too big to scan whole: a window 0.8 m long round each driving axle,
    // on each side, from 0.5 to 2.0 m out, up to the top of the wheels. Only bumps are recorded (the mesh pieces of a frame are not nubs).
    static List<NubPart> AxleWindows(Hits hits, MeshFilter mf, VehicleOut o, string path)
    {
        var list = new List<NubPart>();
        var zs = o.axles.Where(a => a.clip != null).Select(a => Mathf.Round(a.z * 20f) / 20f).Distinct().OrderBy(z => z).ToArray();
        foreach (int side in new[] { -1, 1 })
            foreach (float z in zs)
            {
                var part = new NubPart { path = path, motion = "static-window", note = $"axlebox window side {side} z {z:F2}", phase = 0f };
                var region = new[] { side < 0 ? -2.0f : 0.5f, side < 0 ? -0.5f : 2.0f, z - .4f, z + .4f, 2 * o.wheelRadius + .3f };
                part.islands = new Island[0];
                part.bumps = Bumps(hits, null, new AnimationClip[0], mf, Vector3.zero, Vector3.forward, part, false, region);
                if (part.bumps.Length > 0) list.Add(part);
            }
        return list;
    }

    // Connected pieces of one mesh (vertices welded at 0.2 mm), world space at the current pose. Everything but the largest piece
    // that is 2-30 cm across and has at least 12 triangles is a candidate nub; the top face area and its centre are recorded.
    static Island[] Islands(MeshFilter mf, Vector3 endA, Vector3 endB)
    {
        var mesh = mf.sharedMesh;
        var vs = mesh.vertices;
        var tris = mesh.triangles;
        var parent = new int[vs.Length];
        for (int i = 0; i < parent.Length; i++) parent[i] = i;
        Func<int, int> find = null;
        find = x => { while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; } return x; };
        var weld = new Dictionary<long, int>();
        for (int i = 0; i < vs.Length; i++)
        {
            long key = ((long)Mathf.Round(vs[i].x * 5000f) * 73856093L) ^ ((long)Mathf.Round(vs[i].y * 5000f) * 19349663L) ^ ((long)Mathf.Round(vs[i].z * 5000f) * 83492791L);
            int other;
            if (weld.TryGetValue(key, out other)) parent[find(i)] = find(other); else weld[key] = i;
        }
        for (int t = 0; t + 2 < tris.Length; t += 3) { parent[find(tris[t + 1])] = find(tris[t]); parent[find(tris[t + 2])] = find(tris[t]); }
        var groups = new Dictionary<int, List<int>>();
        for (int t = 0; t + 2 < tris.Length; t += 3)
        {
            int g = find(tris[t]);
            List<int> list;
            if (!groups.TryGetValue(g, out list)) { list = new List<int>(); groups[g] = list; }
            list.Add(t);
        }
        var world = vs.Select(q => mf.transform.TransformPoint(q)).ToArray();
        int biggest = groups.Count == 0 ? 0 : groups.Values.Max(l => l.Count);
        var axis = (mf.transform.TransformPoint(endB) - mf.transform.TransformPoint(endA));
        float length = axis.magnitude; var dir = length > 1e-6f ? axis / length : Vector3.forward;
        var result = new List<Island>();
        foreach (var l in groups.Values)
        {
            if (l.Count < 12 && l.Count != biggest) continue;
            Vector3 lo = world[tris[l[0]]], hi = lo;
            foreach (int t in l) for (int k = 0; k < 3; k++) { var q = world[tris[t + k]]; lo = new Vector3(Mathf.Min(lo.x, q.x), Mathf.Min(lo.y, q.y), Mathf.Min(lo.z, q.z)); hi = new Vector3(Mathf.Max(hi.x, q.x), Mathf.Max(hi.y, q.y), Mathf.Max(hi.z, q.z)); }
            var size = hi - lo;
            bool largest = l.Count == biggest;
            if (!largest && (Mathf.Max(size.x, Mathf.Max(size.y, size.z)) < .02f || Mathf.Max(size.x, Mathf.Max(size.y, size.z)) > .3f)) continue;
            Vector3 top = Vector3.zero; float area = 0;
            foreach (int t in l)
            {
                var a = world[tris[t]]; var b = world[tris[t + 1]]; var c = world[tris[t + 2]];
                var n = Vector3.Cross(b - a, c - a);
                if (n.magnitude < 1e-8f || n.normalized.y < .75f || Mathf.Min(a.y, Mathf.Min(b.y, c.y)) < hi.y - .03f) continue;
                float w = n.magnitude / 2; top += (a + b + c) / 3 * w; area += w;
            }
            var centre = (lo + hi) / 2;
            var topPoint = area > 0 ? top / area : new Vector3(centre.x, hi.y, centre.z);
            result.Add(new Island
            {
                triangles = l.Count, size = V(size), centre = V(centre), top = V(topPoint), local = V(mf.transform.InverseTransformPoint(topPoint)),
                topArea = area, largest = largest,
                alongFromEndA = Vector3.Dot(topPoint - mf.transform.TransformPoint(endA), dir), alongFromEndB = Vector3.Dot(mf.transform.TransformPoint(endB) - topPoint, dir)
            });
        }
        return result.ToArray();
    }

    // The part's own top surface sampled on a 1 cm grid by rays from above (the part and its children only). A bump is a cell that
    // stands at least 6 mm above the median of its surroundings (11 x 11 cells) and is the highest within 2 cm; neighbouring cells
    // 4 mm or more above their surroundings join it. Rise, plateau (cells within 2 mm of the peak), size and place are recorded,
    // then whether a cup on the peak has clear space through the wheel turn.
    static Bump[] Bumps(Hits hits, GameObject go, AnimationClip[] clips, MeshFilter mf, Vector3 endA, Vector3 endB, NubPart part, bool travels, float[] region = null)
    {
        var mr = mf.GetComponent<MeshRenderer>();
        var b = mr.bounds;
        if (region != null)   // x0, x1, z0, z1, top y: only this window of the part
        {
            var lo = new Vector3(Mathf.Max(b.min.x, region[0]), b.min.y, Mathf.Max(b.min.z, region[2]));
            var hi = new Vector3(Mathf.Min(b.max.x, region[1]), Mathf.Min(b.max.y, region[4]), Mathf.Min(b.max.z, region[3]));
            if (hi.x <= lo.x || hi.z <= lo.z || hi.y <= lo.y) return new Bump[0];
            b = new Bounds((lo + hi) / 2, hi - lo); b.min = lo; b.max = hi;
        }
        float step = NubGrid;
        int nx = Mathf.RoundToInt((b.max.x - b.min.x) / step) + 1, nz = Mathf.RoundToInt((b.max.z - b.min.z) / step) + 1;
        while (nx * nz > 10000) { step *= 2; nx = Mathf.RoundToInt((b.max.x - b.min.x) / step) + 1; nz = Mathf.RoundToInt((b.max.z - b.min.z) / step) + 1; }
        part.step = step; part.gridCells = nx * nz;
        var h = new float[nx, nz]; var ok = new bool[nx, nz];
        for (int ix = 0; ix < nx; ix++)
            for (int iz = 0; iz < nz; iz++)
            {
                var origin = new Vector3(b.min.x + ix * step, b.max.y + .05f, b.min.z + iz * step);
                RaycastHit hit;
                if (hits.Ray(origin, Vector3.down, b.max.y - b.min.y + .1f, out hit, mf.transform)) { h[ix, iz] = hit.point.y; ok[ix, iz] = true; }
            }
        int win = Math.Max(2, Mathf.RoundToInt(.05f / step));
        var rise = new float[nx, nz];
        var buf = new List<float>();
        for (int ix = 0; ix < nx; ix++)
            for (int iz = 0; iz < nz; iz++)
            {
                if (!ok[ix, iz]) continue;
                buf.Clear();
                for (int dx = -win; dx <= win; dx++) for (int dz = -win; dz <= win; dz++)
                { int x = ix + dx, z = iz + dz; if (x >= 0 && z >= 0 && x < nx && z < nz && ok[x, z]) buf.Add(h[x, z]); }
                buf.Sort();
                rise[ix, iz] = h[ix, iz] - buf[buf.Count / 2];
            }
        int peakWin = Math.Max(1, Mathf.RoundToInt(.02f / step));
        var seen = new bool[nx, nz];
        var bumps = new List<Bump>();
        for (int ix = 0; ix < nx; ix++)
            for (int iz = 0; iz < nz; iz++)
            {
                if (!ok[ix, iz] || seen[ix, iz] || rise[ix, iz] < NubSeedRise) continue;
                bool peak = true;
                for (int dx = -peakWin; dx <= peakWin && peak; dx++) for (int dz = -peakWin; dz <= peakWin; dz++)
                { int x = ix + dx, z = iz + dz; if (x >= 0 && z >= 0 && x < nx && z < nz && ok[x, z] && h[x, z] > h[ix, iz]) { peak = false; break; } }
                if (!peak) continue;
                // flood the neighbouring raised cells
                var stack = new Stack<int[]>(); var cluster = new List<int[]>();
                stack.Push(new[] { ix, iz }); seen[ix, iz] = true;
                while (stack.Count > 0)
                {
                    var cell = stack.Pop(); cluster.Add(cell);
                    for (int dx = -1; dx <= 1; dx++) for (int dz = -1; dz <= 1; dz++)
                    {
                        int x = cell[0] + dx, z = cell[1] + dz;
                        if (x < 0 || z < 0 || x >= nx || z >= nz || seen[x, z] || !ok[x, z] || rise[x, z] < NubMinRise) continue;
                        seen[x, z] = true; stack.Push(new[] { x, z });
                    }
                }
                int minX = cluster.Min(q => q[0]), maxX = cluster.Max(q => q[0]), minZ = cluster.Min(q => q[1]), maxZ = cluster.Max(q => q[1]);
                float peakY = h[ix, iz];
                var peakPos = new Vector3(b.min.x + ix * step, peakY, b.min.z + iz * step);
                var plateau = cluster.Count(q => h[q[0], q[1]] >= peakY - .002f) * step * step;
                var wa = mf.transform.TransformPoint(endA); var wb = mf.transform.TransformPoint(endB);
                var axis = wb - wa; var dir = axis.magnitude > 1e-6f ? axis.normalized : Vector3.forward;
                bumps.Add(new Bump
                {
                    world = V(peakPos), local = V(mf.transform.InverseTransformPoint(peakPos)),
                    size = new[] { (maxX - minX + 1) * step, (maxZ - minZ + 1) * step }, rise = rise[ix, iz], plateauArea = plateau, peakY = peakY, cells = cluster.Count,
                    alongFromEndA = Vector3.Dot(peakPos - wa, dir), alongFromEndB = Vector3.Dot(wb - peakPos, dir)
                });
            }
        var top = bumps.OrderByDescending(q => q.rise).Take(8).ToList();
        foreach (var bump in top.Take(5))
        {
            var pos = new Vector3(bump.world[0], bump.world[1] + CupPivotAboveBase - CupSeatSink, bump.world[2]);
            string clash;
            if (go == null) { bump.clear = true; bump.clash = "not checked (frame window)"; continue; }
            bump.clear = Clear(hits, go, clips, pos, travels ? mf.transform : null, out clash);
            bump.clash = clash;
        }
        return top.ToArray();
    }


    // ---- pictures ---------------------------------------------------------------------------------------------------
    // Tilted orthographic views of the running gear from outside and above, left and right, in tiles 4.5 m long, with a small marker
    // on every candidate (parented to its part, so it rides with it): magenta = small island (40 triangles or fewer, a top face),
    // cyan = larger island, yellow = bump 1 cm or more, orange = bump 6-10 mm, green = a main-rod end seat that passed.
    static string[] RenderNubs(GameObject go, Transform root, AnimationClip[] clips, VehicleOut o)
    {
        var made = new List<string>();
        var markers = new List<GameObject>();
        var extras = new List<GameObject>();
        var original = new Dictionary<Renderer, Material[]>();
        try
        {
            // The exported Railroader shaders render black in a bare editor scene (the K-28T and T-17 pilot, 2026-10-01): every renderer gets
            // one plain grey Standard material for the pictures, and its own materials back afterwards.
            var grey = new Material(Shader.Find("Standard")) { color = new Color(.62f, .62f, .64f) };
            foreach (var r in go.GetComponentsInChildren<Renderer>(true))
            {
                if (r.sharedMaterials == null || r.sharedMaterials.Length == 0) continue;
                original[r] = r.sharedMaterials;
                r.sharedMaterials = r.sharedMaterials.Select(m => grey).ToArray();
            }
            Sample(go, clips, 0.1f);
            Func<Color, Material> mat = c => new Material(Shader.Find("Unlit/Color")) { color = c };
            Action<Transform, float[], Color, float> mark = (host, local, colour, size) =>
            {
                if (!host || local == null) return;
                var m = GameObject.CreatePrimitive(PrimitiveType.Sphere);
                Object.DestroyImmediate(m.GetComponent<Collider>());
                m.GetComponent<Renderer>().sharedMaterial = mat(colour);
                m.transform.position = host.TransformPoint(new Vector3(local[0], local[1], local[2]));
                m.transform.localScale = Vector3.one * size;
                m.transform.SetParent(host, true);
                markers.Add(m);
            };
            foreach (var part in o.nubParts ?? new NubPart[0])
            {
                var host = root.Find(part.path);
                foreach (var i in part.islands) mark(host, i.local, i.triangles <= 40 && i.topArea > .0003f ? new Color(1f, 0f, 1f) : new Color(0f, 1f, 1f), .03f);
                foreach (var b in part.bumps) if (b.rise >= .006f) mark(host, b.local, b.rise >= .01f ? new Color(1f, 1f, 0f) : new Color(1f, .5f, 0f), .025f);
            }
            foreach (var s in o.endSeats ?? new EndSeat[0])
                if (s.found) mark(root.Find(s.rod), s.local, new Color(0f, 1f, 0f), .04f);
            var sun = new GameObject("sun").AddComponent<Light>(); extras.Add(sun.gameObject);
            sun.type = LightType.Directional; sun.intensity = 1.3f;
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(.6f, .6f, .65f);
            var cam = new GameObject("cam").AddComponent<Camera>(); extras.Add(cam.gameObject);
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(.72f, .78f, .85f);
            cam.orthographic = true; cam.orthographicSize = 1.3f; cam.nearClipPlane = .05f; cam.farClipPlane = 30f;
            var zs = (o.axles ?? new AxleOut[0]).Select(a => a.z).ToArray();
            if (zs.Length == 0 || string.IsNullOrEmpty(OutDir)) return made.ToArray();
            float zMin = zs.Min() - 1.2f, zMax = zs.Max() + 1.4f, tile = 4.5f;
            int n = Mathf.Max(1, Mathf.RoundToInt(Mathf.Ceil((zMax - zMin) / (tile - .4f))));
            n = Mathf.Min(n, 4);
            int width = 1350, height = 780;
            var dir = Path.Combine(OutDir, "oil-renders");
            Directory.CreateDirectory(dir);
            float centreY = Mathf.Max(1.0f, o.wheelRadius + .5f);
            foreach (int side in new[] { -1, 1 })
                for (int k = 0; k < n; k++)
                {
                    float z = n == 1 ? (zMin + zMax) / 2 : zMin + tile / 2 + k * ((zMax - zMin - tile) / (n - 1));
                    sun.transform.rotation = Quaternion.Euler(40, side < 0 ? 90 : -90, 0);   // light travels in from the camera's side, down and across
                    var target = new Vector3(side * 1.0f, centreY, z);
                    cam.transform.position = target + new Vector3(side * 6f * Mathf.Cos(38 * Mathf.Deg2Rad), 6f * Mathf.Sin(38 * Mathf.Deg2Rad), 0f);
                    cam.transform.LookAt(target);
                    var rt = new RenderTexture(width, height, 24);
                    cam.targetTexture = rt; cam.Render(); RenderTexture.active = rt;
                    var tex = new Texture2D(width, height, TextureFormat.RGB24, false);
                    tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                    string name = $"{o.id}-{(side < 0 ? "L" : "R")}{k + 1}.png";
                    File.WriteAllBytes(Path.Combine(dir, name), tex.EncodeToPNG());
                    RenderTexture.active = null; cam.targetTexture = null;
                    Object.DestroyImmediate(rt); Object.DestroyImmediate(tex);
                    made.Add(name);
                }
        }
        catch (Exception e) { Problems.Add(o.id + ": renders: " + e.GetType().Name + ": " + e.Message); }
        finally
        {
            foreach (var kv in original) if (kv.Key) kv.Key.sharedMaterials = kv.Value;
            foreach (var m in markers) if (m) Object.DestroyImmediate(m);
            foreach (var e in extras) if (e) Object.DestroyImmediate(e);
            Sample(go, clips, 0f);
        }
        return made.ToArray();
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
