using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

// Editor-only construction. Runtime uses CCL's supported Button + AnimatorPortReader importers.
public static partial class CclLocoBuild
{
    static void BuildAnimatedToggles(Transform parent)
    {
        var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var cfg in Cfg.AnimatedToggles)
        {
            if (cfg == null || string.IsNullOrWhiteSpace(cfg.Name) || string.IsNullOrWhiteSpace(cfg.Path) ||
                string.IsNullOrWhiteSpace(cfg.AnimKey) || string.IsNullOrWhiteSpace(cfg.Port))
                throw new InvalidOperationException("Animated toggle requires Name, Path, AnimKey and Port.");
            if (!names.Add(Safe(cfg.Name)))
                throw new InvalidOperationException("Animated toggle asset name is not unique: " + cfg.Name);
            if (!AnimatedToggleFinite(cfg.Grip) || !AnimatedToggleFinite(cfg.GripSize) ||
                cfg.GripSize.x <= 0f || cfg.GripSize.y <= 0f || cfg.GripSize.z <= 0f)
                throw new InvalidOperationException("Animated toggle needs a finite grip and positive metre-sized grip box: " + cfg.Name);

            var body = RefBody;
            var source = body.Find(cfg.Path);
            if (!source) throw new InvalidOperationException("Animated toggle source path not found: " + cfg.Path);
            var clip = Clip(cfg.AnimKey);
            if (!clip || clip.length <= 0f) throw new InvalidOperationException("Animated toggle needs a nonempty clip: " + cfg.AnimKey);
            var bindings = AnimationUtility.GetCurveBindings(clip);
            if (bindings.Length == 0 || bindings.Any(b => b.type != typeof(Transform) || string.IsNullOrEmpty(b.path)) ||
                AnimationUtility.GetObjectReferenceCurveBindings(clip).Length != 0 || AnimationUtility.GetAnimationEvents(clip).Length != 0)
                throw new InvalidOperationException("Animated toggle supports only Transform curves on named descendants, without events: " + cfg.AnimKey);
            if (!bindings.Any(b => cfg.Path == b.path || cfg.Path.StartsWith(b.path + "/", StringComparison.Ordinal)))
                throw new InvalidOperationException("Animated toggle source is not moved by its clip: " + cfg.Path);

            clip.SampleAnimation(body.gameObject, 0f);
            Vector3 gripInSource = source.InverseTransformPoint(cfg.Grip);
            var scale = source.lossyScale;
            if (!AnimatedToggleFinite(scale) || Mathf.Min(scale.x, Mathf.Min(scale.y, scale.z)) <= 0f ||
                Mathf.Abs(scale.x - scale.y) > scale.x * 0.0001f || Mathf.Abs(scale.x - scale.z) > scale.x * 0.0001f)
                throw new InvalidOperationException("Animated toggle requires positive uniform source scale to preserve its physical grip size: " + cfg.Name);

            // Copy transforms only, including animated ancestors and their bindings. The exterior remains the sole visual lid.
            var rig = new GameObject("[animated control] " + cfg.Name).transform;
            rig.SetPositionAndRotation(body.position, body.rotation);
            rig.localScale = body.lossyScale;
            rig.SetParent(parent, true);
            var copies = new Dictionary<string, Transform> { { "", rig } };
            foreach (var path in bindings.Select(b => b.path).Concat(new[] { cfg.Path }).Distinct())
                CloneAnimatedTogglePath(body, rig, path, copies);

            var c = Child(copies[cfg.Path], "C_" + cfg.Name, gripInSource);
            c.localScale = new Vector3(1f / scale.x, 1f / scale.y, 1f / scale.z);
            var col = Child(c, "collider", Vector3.zero);
            col.gameObject.AddComponent<BoxCollider>().size = cfg.GripSize;
            var spec = Add(c.gameObject, "CCL.Types.Proxies.Controls.ButtonProxy");
            Set(spec, "createRigidbody", false);
            Set(spec, "useJoints", false);
            Set(spec, "isToggle", true);
            Set(spec, "isTogglingBack", false);
            Set(spec, "pushLocalOffset", Vector3.zero);
            Set(spec, "disableTouchUse", false);
            Interactable(c, col, spec, cfg.Port, -1, false);

            // The same normalization as the exterior avoids the AnimatorPortReader's wrap at exactly one.
            var animators = PortAnimGroups(rig.gameObject, "control follow " + cfg.Name, clip, cfg.Port, 0.999f, 0f);
            if (animators.Count == 0) throw new InvalidOperationException("Animated toggle has no port-driven animator: " + cfg.Name);
            VerifyAnimatedToggle(cfg, body, source, gripInSource, rig, c, clip, animators);
            Line($"  animated toggle {c.name}: {cfg.Port}, source {cfg.Path}, grip {V(cfg.Grip)} size {V(cfg.GripSize)}; click open/close, full source pose, no visual copy");
        }
    }

    static void CloneAnimatedTogglePath(Transform body, Transform rig, string path, Dictionary<string, Transform> copies)
    {
        string current = "";
        var parent = rig;
        foreach (var segment in path.Split('/'))
        {
            if (segment.Length == 0) throw new InvalidOperationException("Animated toggle has an empty path segment: " + path);
            current = current.Length == 0 ? segment : current + "/" + segment;
            if (!copies.TryGetValue(current, out var copy))
            {
                var source = body.Find(current);
                if (!source) throw new InvalidOperationException("Animated toggle clip binding path not found: " + current);
                copy = new GameObject(segment).transform;
                copy.SetParent(parent, false);
                copy.localPosition = source.localPosition;
                copy.localRotation = source.localRotation;
                copy.localScale = source.localScale;
                copies.Add(current, copy);
            }
            parent = copy;
        }
    }

    static void VerifyAnimatedToggle(AnimatedToggleCfg cfg, Transform body, Transform source, Vector3 localGrip,
        Transform rig, Transform control, AnimationClip sourceClip, List<Animator> animators)
    {
        if (rig.GetComponentsInChildren<Renderer>(true).Length != 0 || rig.GetComponentsInChildren<MeshFilter>(true).Length != 0 ||
            rig.GetComponentsInChildren<Rigidbody>(true).Length != 0 || rig.GetComponentsInChildren<Joint>(true).Length != 0)
            throw new InvalidOperationException("Animated toggle follow rig must have no visuals, rigidbodies or joints: " + cfg.Name);
        var clips = animators.Select(a => a.runtimeAnimatorController.animationClips.Distinct().ToArray()).ToArray();
        if (clips.Any(cs => cs.Length != 1)) throw new InvalidOperationException("Animated toggle expected one generated clip per animator: " + cfg.Name);
        float maxError = 0f;
        try
        {
            foreach (float phase in new[] { 0f, 0.25f, 0.5f, 0.75f, 1f })
            {
                float normalized = phase * 0.999f;
                sourceClip.SampleAnimation(body.gameObject, normalized * sourceClip.length);
                // Parent animator first when a source clip has several independent regions.
                foreach (int i in Enumerable.Range(0, animators.Count).OrderBy(i => AnimatedToggleDepth(animators[i].transform)))
                    clips[i][0].SampleAnimation(animators[i].gameObject, normalized * clips[i][0].length);
                Vector3 expected = source.TransformPoint(localGrip);
                float error = Vector3.Distance(control.position, expected);
                float angle = Quaternion.Angle(control.rotation, source.rotation);
                float sizeError = Vector3.Distance(control.lossyScale, Vector3.one);
                if (!AnimatedToggleFinite(control.position) || !AnimatedToggleFinite(control.lossyScale) || error > 0.001f || angle > 0.05f || sizeError > 0.001f)
                    throw new InvalidOperationException($"Animated toggle {cfg.Name} phase {phase:F2} failed source alignment: {error:F6} m, {angle:F3} deg, scale {V(control.lossyScale)}.");
                maxError = Mathf.Max(maxError, error);
                Line($"  animated toggle check {cfg.Name} phase {phase:F2}: source grip {V(expected)}, control {V(control.position)}, error {error:F7} m");
            }
        }
        finally
        {
            sourceClip.SampleAnimation(body.gameObject, 0f);
            foreach (int i in Enumerable.Range(0, animators.Count).OrderBy(i => AnimatedToggleDepth(animators[i].transform)))
                clips[i][0].SampleAnimation(animators[i].gameObject, 0f);
        }
        Line($"  animated toggle verified {cfg.Name}: 5 phases, max error {maxError:F7} m, no copied renderers");
    }

    static bool AnimatedToggleFinite(Vector3 v) => !float.IsNaN(v.x) && !float.IsInfinity(v.x) &&
        !float.IsNaN(v.y) && !float.IsInfinity(v.y) && !float.IsNaN(v.z) && !float.IsInfinity(v.z);

    static int AnimatedToggleDepth(Transform t)
    {
        int result = 0;
        while (t.parent) { result++; t = t.parent; }
        return result;
    }
}
