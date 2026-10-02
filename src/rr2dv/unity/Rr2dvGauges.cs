using System;
using System.IO;
using System.Linq;
using CCL.Types.Components;
using CCL.Types.Proxies.Controls;
using CCL.Types.Proxies.Indicators;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

// Editor-only assembly construction. Exported instruments contain CCL proxies/grabbers only.
// Common donor geometry/calibration is separate from the measured car-specific fitting input.
public static partial class CclLocoBuild
{
    [Serializable] public class GaugeFit
    {
        public string sourceGauge, reading, supportPath, evidence;
        public float[] position, rotation, supportPoint;
        public float scale;
    }
    [Serializable] public class GaugeSelection
    {
        public int schema;
        public string carId, state;
        public GaugeFit[] instruments;
    }
    [Serializable] class GaugeBuildInput { public GaugeSelection gauges; }

    static GaugeSelection ReadRr2dvGaugeSelection()
    {
        string path = Path.Combine(Application.dataPath, "Rr2dv/BuildInput.json");
        if (!File.Exists(path)) return null;
        var selection = JsonUtility.FromJson<GaugeBuildInput>(File.ReadAllText(path)).gauges;
        if (selection == null || selection.carId != CarId) return null; // no fleet/tender deployment
        if (selection.schema != 1 || selection.instruments == null || selection.instruments.Length == 0)
            throw new InvalidDataException("Unsupported or empty gauge pilot selection");
        return selection;
    }

    static Vector3 GaugeVector(float[] values)
    {
        if (values == null || values.Length != 3 || values.Any(v => float.IsNaN(v) || float.IsInfinity(v)))
            throw new InvalidDataException("Gauge fitting requires a finite three-component vector");
        return new Vector3(values[0], values[1], values[2]);
    }

    static Quaternion GaugeRotation(float[] values)
    {
        if (values == null || values.Length != 4 || values.Any(v => float.IsNaN(v) || float.IsInfinity(v)) ||
            Mathf.Abs(values.Sum(v => v * v) - 1f) > .001f)
            throw new InvalidDataException("Gauge fitting requires a unit quaternion");
        return new Quaternion(values[0], values[1], values[2], values[3]);
    }

    static Transform S060GaugePart(Transform parent, string name, string mesh, string material, Vector3 position)
    {
        if (!MeshGrabber.MeshNames.Contains(mesh) || !MaterialGrabber.MaterialNames.Contains(material))
            throw new InvalidDataException("Unavailable CCL gauge resource: " + mesh + " / " + material);
        var part = Child(parent, name, position);
        var filter = part.gameObject.AddComponent<MeshFilter>();
        var renderer = part.gameObject.AddComponent<MeshRenderer>();
        // A slot is required for the material grabber. No game bytes or replacement-looking fallback mesh are baked in.
        renderer.sharedMaterial = ownMats["needle_black"];
        var meshGrabber = part.gameObject.AddComponent<MeshGrabberFilter>();
        meshGrabber.Filter = filter; meshGrabber.ReplacementName = mesh;
        AddGaugeMaterialGrabber(renderer, material);
        return part;
    }

    static void AddGaugeMaterialGrabber(Renderer renderer, string material)
    {
        if (!MaterialGrabber.MaterialNames.Contains(material))
            throw new InvalidDataException("Unavailable CCL gauge material: " + material);
        var grabber = renderer.GetComponent<MaterialGrabberRenderer>() ?? renderer.gameObject.AddComponent<MaterialGrabberRenderer>();
        grabber.RenderersToAffect = new[] { renderer };
        grabber.Replacements = new[] { new MaterialGrabberRenderer.IndexToName {
            RendererIndex = 0, ReplacementName = material } };
        grabber.OnValidate(); // CCL imports the serialized JSON, not merely the editor array
    }

    static IndicatorGaugeProxy BuildS060Pressuremeter(Transform gauge, string port)
    {
        S060GaugePart(gauge, "housing", "s060_gauge_pressuremeter", "LocoS060_Interior", Vector3.zero);
        S060GaugePart(gauge, "face", "s060_gauge_label_pressuremeter", "LocoS060_Gauges", Vector3.zero);
        S060GaugePart(gauge, "glass", "s060_gauge_glass_pressuremeter", "GlassIndoors", Vector3.zero);
        var needle = S060GaugePart(gauge, "needle", "s060_needle_pressuremeter", "LocoS060_Gauges",
            new Vector3(0, -.0000114440918f, -.0283780098f));
        var host = Child(gauge, "reader", new Vector3(.000078054145f, -.0000114440918f, -.0284676570f));
        host.localRotation = new Quaternion(0, -.00872650743f, 0, .999961972f);
        var indicator = host.gameObject.AddComponent<IndicatorGaugeProxy>();
        indicator.needle = needle;
        // Actual B99 S060 serialized values, checked against its 0..18 bar dial.
        // DV pressure is absolute: atmosphere (1 bar) corresponds to printed zero.
        indicator.minValue = 1f; indicator.maxValue = 19f;
        indicator.minAngle = -135f; indicator.maxAngle = 135f;
        indicator.rotationAxis = Vector3.back; indicator.unclamped = false;
        needle.localRotation = Quaternion.AngleAxis(indicator.minAngle, indicator.rotationAxis);
        var reader = host.gameObject.AddComponent<IndicatorPortReaderProxy>();
        reader.portId = port; reader.valueMultiplier = 1f;
        return indicator;
    }

    static void ValidateRr2dvGaugeSupport(GaugeFit fit)
    {
        var surfaces = RefBody.GetComponentsInChildren<MeshFilter>(false).Where(f => f.sharedMesh &&
            (AnimationUtility.CalculateTransformPath(f.transform, RefBody) == fit.supportPath || AnimationUtility.CalculateTransformPath(f.transform, RefBody).EndsWith("/" + fit.supportPath))).ToArray();
        if (surfaces.Length != 1) throw new InvalidDataException("Gauge support must resolve uniquely: " + fit.supportPath);
        var temporary = new GameObject("[gauge support check]");
        temporary.transform.SetParent(surfaces[0].transform, false);
        try
        {
            var collider = temporary.AddComponent<MeshCollider>(); collider.sharedMesh = surfaces[0].sharedMesh;
            Physics.SyncTransforms();
            var rotation = GaugeRotation(fit.rotation); var centre = GaugeVector(fit.position);
            var front = rotation * Vector3.back; int contacts = 0;
            for (int i = 0; i < 9; i++)
            {
                float angle = (i - 1) * Mathf.PI / 4;
                var radial = i == 0 ? Vector3.zero : new Vector3(Mathf.Cos(angle), Mathf.Sin(angle), 0) * .06f;
                var rear = centre + rotation * (new Vector3(0, 0, .015117139f) + radial) * fit.scale;
                var hits = Physics.RaycastAll(rear + front * .05f, -front, .10f)
                    .Where(h => h.collider == collider).OrderBy(h => h.distance).ToArray();
                if (hits.Length == 0) continue;
                float gap = hits[0].distance - .05f;
                if (gap < -.001f) throw new InvalidDataException("Pressuremeter housing intersects its support");
                if (gap <= .004f) contacts++;
            }
            if (contacts < 7) throw new InvalidDataException("Pressuremeter rear mounting pad lacks verified support: " + contacts + "/9");
            var datum = centre + rotation * new Vector3(0, 0, .017117139f) * fit.scale;
            if ((datum - GaugeVector(fit.supportPoint)).sqrMagnitude > .000004f)
                throw new InvalidDataException("Gauge support datum no longer matches the measured fitting");
            Line("rr2dv gauge rear mounting pad: " + contacts + "/9 support samples; driver/control clearance still pending");
        }
        finally { Object.DestroyImmediate(temporary); }
    }

    static void BuildRr2dvGauges()
    {
        var selection = ReadRr2dvGaugeSelection(); if (selection == null) return;
        string path = $"{carFolder}/{CarId}_interior.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var hud = root.GetComponent<LocoIndicatorReaderProxy>();
            if (!hud) throw new InvalidDataException("Gauge pilot has no HUD indicator reader");
            foreach (var fit in selection.instruments)
            {
                if (fit.reading != "boiler") throw new InvalidDataException("Initial pressuremeter pilot supports boiler only; other fittings await pilot acceptance");
                var matches = root.GetComponentsInChildren<Transform>(true).Where(t => t.name == "gauge " + fit.sourceGauge).ToArray();
                if (matches.Length != 1 || fit.sourceGauge != Cfg.MainPressureGauge)
                    throw new InvalidDataException("Pilot main boiler gauge must resolve uniquely");
                ValidateRr2dvGaugeSupport(fit);
                var gauge = matches[0];
                foreach (Transform child in gauge.Cast<Transform>().ToArray()) Object.DestroyImmediate(child.gameObject);
                gauge.SetPositionAndRotation(GaugeVector(fit.position), GaugeRotation(fit.rotation));
                gauge.localScale = Vector3.one * fit.scale;
                hud.steam = BuildS060Pressuremeter(gauge, "boiler.PRESSURE");
                var pad = GameObject.CreatePrimitive(PrimitiveType.Cube);
                pad.name = "mounting pad"; pad.transform.SetParent(gauge, false);
                pad.transform.localPosition = new Vector3(0, 0, .016117139f);
                pad.transform.localScale = new Vector3(.10f, .10f, .002f);
                Object.DestroyImmediate(pad.GetComponent<Collider>());
                pad.GetComponent<MeshRenderer>().sharedMaterial = ownMats["needle_black"];
                Child(gauge, "mount datum", new Vector3(0, 0, .017117139f));
                Line("rr2dv gauge pilot " + fit.sourceGauge + ": S060 housing/face/glass/needle; boiler.PRESSURE 1..19 absolute -> 0..18 bar printed; CCL resolution and game acceptance pending");
            }
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // The pinned LOD builder strips all MonoBehaviours. Restore only resource grabbers, with references to the LOD's
    // own filters/renderers, so the render-only copy can also resolve donor meshes/materials at game load.
    static void RestoreRr2dvGaugeLodGrabbers()
    {
        var selection = ReadRr2dvGaugeSelection(); if (selection == null) return;
        var interior = AssetDatabase.LoadAssetAtPath<GameObject>($"{carFolder}/{CarId}_interior.prefab");
        string path = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            var lod = root.transform.Find("[interior LOD]");
            if (!lod) throw new InvalidDataException("Gauge pilot has no interior LOD");
            foreach (var source in interior.GetComponentsInChildren<MeshGrabberFilter>(true))
            {
                var target = lod.Find(AnimationUtility.CalculateTransformPath(source.transform, interior.transform));
                if (!target || !target.GetComponent<MeshFilter>()) throw new InvalidDataException("Gauge LOD resource target is missing");
                var grabber = target.GetComponent<MeshGrabberFilter>() ?? target.gameObject.AddComponent<MeshGrabberFilter>();
                grabber.Filter = target.GetComponent<MeshFilter>(); grabber.ReplacementName = source.ReplacementName;
                var material = source.GetComponent<MaterialGrabberRenderer>(); material.AfterImport();
                AddGaugeMaterialGrabber(target.GetComponent<MeshRenderer>(), material.Replacements.Single().ReplacementName);
            }
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }
}
