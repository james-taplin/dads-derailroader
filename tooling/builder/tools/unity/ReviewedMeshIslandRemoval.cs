using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

// Generic build-time removal of complete, explicitly reviewed source mesh islands.
// No source asset is mutated; the supplied mesh writer persists only the rebuilt clone.
public static class ReviewedMeshIslandRemoval
{
    public static void Apply(GameObject body, RemovedMeshIslandCfg[] removals,
        Func<Mesh, List<List<(int sub, int a, int b, int c)>>> islands,
        Func<Mesh, List<(int sub, int a, int b, int c)>, Mesh> submesh,
        Func<Mesh, string, Mesh> save, Action<string> log)
    {
        if (removals == null || removals.Length == 0) return;
        // One millimetre permits the measured coordinates' rounding and transform floating-point
        // error at source scale 100; centroid, size and triangle count must all match uniquely.
        const float tolerance = 0.001f;
        foreach (var set in removals.GroupBy(x => x.Part))
        {
            var part = body.transform.Find(set.Key);
            var mf = part ? part.GetComponent<MeshFilter>() : null;
            if (!mf || !mf.sharedMesh) throw new InvalidOperationException("Removed mesh island part missing: " + set.Key);
            var source = mf.sharedMesh;
            var vertices = source.vertices;
            var groups = islands(source);
            Bounds BoundsOf(List<(int sub, int a, int b, int c)> group)
            {
                var bounds = new Bounds(part.TransformPoint(vertices[group[0].a]), Vector3.zero);
                foreach (var triangle in group)
                {
                    bounds.Encapsulate(part.TransformPoint(vertices[triangle.a]));
                    bounds.Encapsulate(part.TransformPoint(vertices[triangle.b]));
                    bounds.Encapsulate(part.TransformPoint(vertices[triangle.c]));
                }
                return bounds;
            }
            var boundsList = groups.Select(BoundsOf).ToArray();
            var removed = new HashSet<int>();
            foreach (var entry in set)
            {
                if (string.IsNullOrEmpty(entry.Name) || entry.ExpectedTriangles < 1)
                    throw new InvalidOperationException("Removed mesh island requires name and positive expected triangles: " + set.Key);
                var matches = Enumerable.Range(0, groups.Count).Where(i =>
                    groups[i].Count == entry.ExpectedTriangles &&
                    Vector3.Distance(boundsList[i].center, entry.Centre) < tolerance &&
                    Vector3.Distance(boundsList[i].size, entry.Size) < tolerance).ToArray();
                if (matches.Length != 1 || !removed.Add(matches[0]))
                    throw new InvalidOperationException($"Reviewed island {entry.Name} on {set.Key}: expected one unique match, found {matches.Length}");
                log($"  removed reviewed mesh island {entry.Name}: {entry.ExpectedTriangles} triangles, centre {boundsList[matches[0]].center}, size {boundsList[matches[0]].size}");
            }
            var retained = groups.Where((group, i) => !removed.Contains(i)).SelectMany(group => group).ToList();
            if (retained.Count == 0) throw new InvalidOperationException("Reviewed removal would empty mesh: " + set.Key);
            string safeName = string.Concat(set.Key.Select(c => char.IsLetterOrDigit(c) ? c : '_'));
            var output = save(submesh(source, retained), "reviewed_removed_" + safeName);
            mf.sharedMesh = output;
            foreach (var collider in part.GetComponents<MeshCollider>())
                if (collider.sharedMesh == source) collider.sharedMesh = output;
        }
    }
}
