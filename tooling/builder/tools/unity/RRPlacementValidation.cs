using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

// Shared build gate for modelled drawbars and DV's stock external fittings.
// Source geometry and the runtime stock fitting dimensions are checked before export.
public static class RRPlacementValidation
{
    public static IEnumerable<string> Validate(LocoConfig loco)
    {
        var lines = new List<string>();
        if (loco.Tender != null)
        {
            var tender = loco.Tender;
            if (!loco.RrEndRear.HasValue || !tender.RrEndFront.HasValue)
                throw new InvalidOperationException("Modelled loco-tender joint needs both Railroader car ends");
            float offset = loco.RrEndRear.Value - 1f - tender.RrEndFront.Value;
            float rearPlane = loco.RrEndRear.Value - .5f;
            float frontPlane = tender.RrEndFront.Value + .5f;
            if (Mathf.Abs(rearPlane - frontPlane - offset) > .001f)
                throw new InvalidOperationException("Railroader drawbar planes do not reproduce the tender offset");
            lines.Add($"RR tender spacing: loco end {loco.RrEndRear.Value:F3} - 1.000 - tender end {tender.RrEndFront.Value:F3} = offset {offset:F3} m");
            if (loco.CoupledPin != null && tender.CoupledPin != null)
            {
                var a = loco.CoupledPin; var b = tender.CoupledPin;
                CheckPinSource(loco, a); CheckPinSource(tender, b);
                float dz = Mathf.Abs(a.Centre.z - (b.Centre.z + offset));
                float dx = Mathf.Abs(a.Centre.x - b.Centre.x);
                float verticalOverlap = Mathf.Min(a.Centre.y + a.Size.y / 2f, b.Centre.y + b.Size.y / 2f)
                    - Mathf.Max(a.Centre.y - a.Size.y / 2f, b.Centre.y - b.Size.y / 2f);
                if (dz <= .5f && (dz > .03f || dx > .05f || verticalOverlap < .03f))
                    throw new InvalidOperationException($"Modelled mating pins misalign at RR spacing: z {dz:F3} m, x {dx:F3} m, vertical overlap {verticalOverlap:F3} m");
                lines.Add(dz <= .5f ? $"mating pin pair: z {dz:F3} m, x {dx:F3} m, vertical overlap {verticalOverlap:F3} m"
                    : $"distinct pin features: z separation {dz:F3} m at RR spacing; do not force alignment");
            }
            else lines.Add("no verified mating pin pair; Railroader end spacing governs the joint");
        }
        return lines;
    }

    // The core calls this after auto-placement/exact overrides, before saving the interactables prefab.
    public static IEnumerable<string> ValidateFinalFittings(LocoConfig cfg, GameObject body, Transform wheel, Transform release)
    {
        var lines = new List<string>();
        var enabled = body.GetComponentsInChildren<Collider>(true).Where(c => c.enabled).ToArray();
        try
        {
            if (cfg.HandbrakeWheel != null)
            {
                if (!wheel) throw new InvalidOperationException(cfg.CarId + " missing final handwheel");
                CheckHandbrake(cfg, body, lines, (wheel.localPosition, wheel.localEulerAngles));
            }
            if (cfg.BrakeRelease != null)
            {
                if (!release) throw new InvalidOperationException(cfg.CarId + " missing final release");
                if (cfg.BrakeReleaseSideX.HasValue || cfg.BrakeReleaseBoardBottomY.HasValue)
                    CheckRelease(cfg, body, lines, (release.localPosition, release.localEulerAngles));
                else CheckReleaseClearance(cfg, body, release, lines);
            }
        }
        finally { foreach (var collider in enabled) if (collider) collider.enabled = true; }
        return lines;
    }

    static void CheckReleaseClearance(LocoConfig cfg, GameObject body, Transform release, List<string> lines)
    {
        var position = release.localPosition; var rotation = release.localRotation;
        var outward = rotation * Vector3.forward; var up = rotation * Vector3.up;
        if (Mathf.Abs(outward.x) < .98f || Mathf.Abs(outward.y) > .05f || Mathf.Abs(outward.z) > .05f)
            throw new InvalidOperationException(cfg.CarId + " release must point transversely outward");
        var added = new List<GameObject>();
        foreach (var old in body.GetComponentsInChildren<Collider>(true)) old.enabled = false;
        try
        {
            foreach (var mf in body.GetComponentsInChildren<MeshFilter>(false))
            {
                var renderer = mf.GetComponent<MeshRenderer>();
                if (!mf.sharedMesh || !renderer || !renderer.enabled) continue;
                var go = new GameObject("validation surface"); go.transform.SetParent(mf.transform, false);
                go.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh; added.Add(go);
            }
            Physics.SyncTransforms();
            var skin = Surface(position, outward);
            if (!skin.HasValue || Vector3.Dot(skin.Value.point - position, outward) < .10f)
                throw new InvalidOperationException(cfg.CarId + " release valve body is not behind source skin");
            var tip = position + outward * 1.067645f;
            var tipSkin = Surface(tip, outward);
            if (!tipSkin.HasValue || Vector3.Dot(tip - tipSkin.Value.point, outward) < .05f)
                throw new InvalidOperationException(cfg.CarId + " release handle not exposed");
            // A bracket may end inside a tender tank; never let it penetrate the occupied cab.
            var bracket = position + outward * .8f; var top = bracket + up * .431255f;
            if (!cfg.IsTender && cfg.CabTeleportVolume.HasValue)
            {
                var (centre, size) = cfg.CabTeleportVolume.Value;
                if (new Bounds(centre, size + Vector3.one * .2f).Contains(top))
                    foreach (var dx in new[] { -.01f, 0f, .01f })
                        foreach (var dz in new[] { -.01f, 0f, .01f })
                            if (Physics.RaycastAll(bracket + new Vector3(dx, 0, dz), up, .428255f)
                                .Any(h => h.collider.name == "validation surface"))
                                throw new InvalidOperationException(cfg.CarId + " scaled release bracket intersects occupied cab geometry");
            }
            if (Mathf.Min(position.y - .080590f, top.y) < .3f)
                throw new InvalidOperationException(cfg.CarId + " release is below clearance floor");
            lines.Add($"{cfg.CarId} final stock release: outward handle, valve behind skin; scaled bracket .431255 m checked at {position} ({(cfg.BrakeReleaseExact ? "exact" : "automatic")})");
        }
        finally { foreach (var go in added) Object.DestroyImmediate(go); }
    }

    static void CheckPinSource(LocoConfig cfg, ModelPin pin)
    {
        var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(cfg.SrcPrefab);
        if (!prefab) throw new InvalidOperationException("Drawbar source prefab missing: " + cfg.SrcPrefab);
        var root = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
        try
        {
            Bounds area = new Bounds(pin.Centre, pin.Size + Vector3.one * .02f);
            int triangles = 0;
            foreach (var mf in root.GetComponentsInChildren<MeshFilter>(true))
            {
                if (!mf.sharedMesh) continue;
                var verts = mf.sharedMesh.vertices; var indices = mf.sharedMesh.triangles;
                for (int i = 0; i < indices.Length; i += 3)
                    if (area.Contains(mf.transform.TransformPoint(verts[indices[i]])) &&
                        area.Contains(mf.transform.TransformPoint(verts[indices[i+1]])) &&
                        area.Contains(mf.transform.TransformPoint(verts[indices[i+2]]))) triangles++;
            }
            if (triangles < pin.MinTriangles)
                throw new InvalidOperationException($"{cfg.CarId} drawbar pin source geometry missing near {pin.Centre}: {triangles} triangles, need {pin.MinTriangles}");
        }
        finally { Object.DestroyImmediate(root); }
    }

    static void CheckHandbrake(LocoConfig cfg, GameObject body, List<string> lines, (Vector3 position, Vector3 euler) pose)
    {
        var (position, euler) = pose;
        Quaternion rotation = Quaternion.Euler(euler);
        Vector3 outward = rotation * Vector3.forward;
        var added = new List<GameObject>();
        foreach (var existing in body.GetComponentsInChildren<Collider>(true)) existing.enabled = false;
        foreach (var mf in body.GetComponentsInChildren<MeshFilter>(true))
        {
            if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0) continue;
            var holder = new GameObject("validation surface"); holder.transform.SetParent(mf.transform, false);
            holder.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
            added.Add(holder);
        }
        try
        {
            Physics.SyncTransforms();
            var centre = Surface(position, outward);
            if (!centre.HasValue) throw new InvalidOperationException(cfg.CarId + " handbrake has no modelled mounting surface");
            float standOff = Vector3.Dot(position - centre.Value.point, outward);
            if (Vector3.Dot(centre.Value.normal, outward) < .90f || standOff < .03f || standOff > .08f)
                throw new InvalidOperationException($"{cfg.CarId} handbrake mount misfit: stand-off {standOff:F3} m, outward normal {Vector3.Dot(centre.Value.normal,outward):F3}");
            // The real replacement wheel has a 0.207455 m swept radius and its rim begins at local z .037896.
            // Only its short mounting shaft at local z -0.061302 may enter the body.
            float least = float.PositiveInfinity; int hits = 0;
            for (int i = 0; i < 24; i++)
            {
                float angle = i * Mathf.PI * 2f / 24f;
                Vector3 ring = position + rotation * new Vector3(.207455f * Mathf.Cos(angle), .207455f * Mathf.Sin(angle), .037896f);
                var skin = Surface(ring, outward);
                if (!skin.HasValue) continue;
                hits++;
                least = Mathf.Min(least, Vector3.Dot(ring - skin.Value.point, outward));
            }
            if (hits < 12 || least < .025f)
                throw new InvalidOperationException($"{cfg.CarId} handbrake rotating rim clips model: {hits}/24 surface hits, least clearance {least:F3} m");
            lines.Add($"{cfg.CarId} stock handbrake: +z outward, shaft mount {standOff:F4} m, rotating rim clearance >= {least:F4} m ({hits}/24 samples)");
        }
        finally { foreach (var go in added) Object.DestroyImmediate(go); }
    }

    static RaycastHit? Surface(Vector3 point, Vector3 outward)
    {
        return Physics.RaycastAll(point + outward * 1.5f, -outward, 3f)
            .Where(x => x.collider.name == "validation surface")
            .OrderBy(x => x.distance).Select(x => (RaycastHit?)x).FirstOrDefault();
    }

    static void CheckRelease(LocoConfig cfg, GameObject body, List<string> lines, (Vector3 position, Vector3 euler) pose)
    {
        if (!cfg.BrakeReleaseSideX.HasValue || !cfg.BrakeReleaseBoardBottomY.HasValue)
            throw new InvalidOperationException(cfg.CarId + " brake release needs measured side skin and running-board underside");
        var (position, euler) = pose;
        Quaternion rotation = Quaternion.Euler(euler);
        Vector3 outward = rotation * Vector3.forward;
        Vector3 supportUp = rotation * Vector3.up;
        float side = cfg.BrakeReleaseSideX.Value;
        float signed = Mathf.Sign(outward.x);
        if (Mathf.Abs(outward.x) < .98f || Mathf.Abs(outward.y) > .05f || Mathf.Abs(outward.z) > .05f)
            throw new InvalidOperationException(cfg.CarId + " brake release rod must point transversely outward");
        float cube = signed * position.x;
        float nearRed = signed * (position.x + outward.x * .8574f);
        float redTip = signed * (position.x + outward.x * 1.067645f);
        float supportEndY = position.y + .431255f * supportUp.y;
        float highest = Mathf.Max(position.y + .080590f, supportEndY);
        float lowest = Mathf.Min(position.y - .080590f, supportEndY);
        // Compare the supplied model landmarks to the actual source skin at the root
        // height and the underside immediately above the red puller.
        var added = new List<GameObject>();
        foreach (var old in body.GetComponentsInChildren<Collider>(true)) old.enabled = false;
        foreach (var mf in body.GetComponentsInChildren<MeshFilter>(true))
        {
            if (!mf.sharedMesh || mf.sharedMesh.vertexCount == 0) continue;
            var holder = new GameObject("validation surface"); holder.transform.SetParent(mf.transform, false);
            holder.AddComponent<MeshCollider>().sharedMesh = mf.sharedMesh;
            added.Add(holder);
        }
        float actualSide, actualBoard;
        try
        {
            Physics.SyncTransforms();
            var skin = Physics.RaycastAll(new Vector3(signed * 3f, position.y, position.z), -outward, 3f)
                .Where(h => h.collider.name == "validation surface")
                .OrderBy(h => h.distance).ToArray();
            if (skin.Length == 0) throw new InvalidOperationException(cfg.CarId + " brake release lacks a measured side skin at its mounting height");
            actualSide = signed * skin[0].point.x;
            var roof = Physics.RaycastAll(new Vector3(signed * redTip, position.y - .5f, position.z), Vector3.up, 2f)
                .Where(h => h.collider.name == "validation surface" && h.point.y > highest)
                .OrderBy(h => h.distance).ToArray();
            if (roof.Length == 0) throw new InvalidOperationException(cfg.CarId + " brake release has no measured running-board underside above the red puller");
            actualBoard = roof[0].point.y;
        }
        finally { foreach (var go in added) Object.DestroyImmediate(go); }
        if (Mathf.Abs(side-actualSide) > .1f || Mathf.Abs(cfg.BrakeReleaseBoardBottomY.Value-actualBoard) > .12f)
            throw new InvalidOperationException($"{cfg.CarId} brake release landmarks stale: side {side:F3}/{actualSide:F3}, board {cfg.BrakeReleaseBoardBottomY.Value:F3}/{actualBoard:F3}");
        side = actualSide;
        if (cube + .1f > side - .5f || nearRed > side + .03f || redTip < side + .05f || redTip > side + .30f ||
            highest > actualBoard - .02f || lowest < .30f)
            throw new InvalidOperationException($"{cfg.CarId} brake release fit: cube {cube:F3}, red {nearRed:F3}..{redTip:F3}, actual side {side:F3}, vertical {lowest:F3}..{highest:F3}, board bottom {actualBoard:F3}");
        lines.Add($"{cfg.CarId} stock brake release: cube {side-cube:F3} m inside measured side; red tip {redTip-side:F3} m exposed; highest part {actualBoard-highest:F3} m below measured board");
    }
}
