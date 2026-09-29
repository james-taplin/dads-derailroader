using System;
using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;
using CCL.Types.Proxies.Ports;
using CCL.Types.Proxies.Simulation;
using Object = UnityEngine.Object;

// Source-declared targets and complete clips, never a vehicle name or the first rotating bone.
public static partial class CclLocoBuild
{
    [Serializable] class RrToggleAnimation { public string clipName; }
    [Serializable] class RrToggleTarget { public string[] path; }
    [Serializable] class RrToggleData
    {
        public RrToggleAnimation animation;
        public RrToggleTarget targetColliderObject;
        public string key, title;
        public float speed = 1f;
        public bool enabled = true;
    }
    class RrOpening
    {
        public string name, clip, target, hinge, port;
        public string[] roots;
        public float transitionTime;
        public bool clickToggle;
        public AnimationClip motion;
    }
    static readonly List<RrOpening> RrOpenings = new List<RrOpening>();

    static string[] paths0(EditorCurveBinding[] bindings) => bindings.Select(b => b.path).Distinct().ToArray();

    static void PrepareRr2dvInteractions()
    {
        RrOpenings.Clear();
        var removed = new HashSet<string>(Cfg.CabControlObjects);
        var noWalk = new HashSet<string>(Cfg.NoWalkParts);
        var ports = new HashSet<string>(Cfg.SimControls);
        foreach (var component in Cfg.Components.Where(c => c.kind == "ToggleAnimation"))
        {
            var data = JsonUtility.FromJson<RrToggleData>(component.extra);
            if (!data.enabled || (data.title ?? "").IndexOf("firebox", StringComparison.OrdinalIgnoreCase) >= 0 ||
                string.Equals(data.key, "cylCock", StringComparison.OrdinalIgnoreCase) ||
                (data.title ?? "").IndexOf("cylinder cocks", StringComparison.OrdinalIgnoreCase) >= 0) continue;
            var key = data.animation?.clipName;
            if (string.IsNullOrEmpty(key) || !Cfg.AnimationMap.ContainsKey(key))
                { LeaveOutOpening(component.name, "Toggle has no resolved source clip: " + component.name); continue; }
            string target = string.Join("/", data.targetColliderObject?.path ?? new string[0]);
            if (string.IsNullOrEmpty(target) || !RefBody.Find(target))
                { LeaveOutOpening(component.name, "Toggle has no resolved declared target: " + component.name + " / " + target); continue; }
            var targetNode = RefBody;
            bool ambiguous = false;
            foreach (var segment in target.Split('/'))
            {
                var matches = targetNode.Cast<Transform>().Where(t => t.name == segment).ToArray();
                if (matches.Length != 1) { ambiguous = true; break; }
                targetNode = matches[0];
            }
            if (ambiguous) { LeaveOutOpening(component.name, "Ambiguous declared toggle target: " + target); continue; }
            var clip = Clip(key);
            var bindings = AnimationUtility.GetCurveBindings(clip);
            if (clip.length <= 0 || bindings.Length == 0 || bindings.Any(b => b.type != typeof(Transform) || string.IsNullOrEmpty(b.path)) ||
                AnimationUtility.GetObjectReferenceCurveBindings(clip).Length != 0 || AnimationUtility.GetAnimationEvents(clip).Length != 0)
                { LeaveOutOpening(component.name, "Toggle requires a nonempty Transform-only clip without events: " + key); continue; }
            if (paths0(bindings).Any(p => !RefBody.Find(p))) { LeaveOutOpening(component.name, "Unresolved toggle binding: " + key); continue; }
            // Only parts the clip moves belong to the opening. A Blender export can key every animated part in every
            // clip with flat curves (DM&IR M-3: 11 of 12 cab toggles left out as overlapping the first door, 2026-09-29).
            var paths = bindings.GroupBy(b => b.path)
                .Where(g => g.Any(b => { var keys = AnimationUtility.GetEditorCurve(clip, b).keys; return keys.Length > 0 && keys.Any(k => Mathf.Abs(k.value - keys[0].value) > 1e-4f); }))
                .Select(g => g.Key).ToArray();
            if (paths.Length == 0) { LeaveOutOpening(component.name, "Toggle clip moves nothing: " + key); continue; }
            if (paths.Length < paths0(bindings).Length)
                Line($"rr2dv opening source {key}: {paths0(bindings).Length - paths.Length} keyed but unmoved transform(s) ignored");
            var ancestors = paths.Where(p => target == p || target.StartsWith(p + "/", StringComparison.Ordinal)).OrderBy(p => p.Length).ToArray();
            // A rigged opening declares its armature as the target and the clip moves the bones inside it (H9 windows,
            // deflectors and roof hatch, 2026-09-28): the whole declared assembly moves as one, with its skinned mesh.
            bool rigged = ancestors.Length == 0 && paths.All(p => p.StartsWith(target + "/", StringComparison.Ordinal));
            if (rigged) ancestors = paths.OrderBy(p => p.Split('/').Length).ThenBy(p => p, StringComparer.Ordinal).Take(1).ToArray();
            if (ancestors.Length == 0) { LeaveOutOpening(component.name, "Declared toggle target is not moved by its clip: " + key + " / " + target); continue; }
            var existing = RrOpenings.FirstOrDefault(o => o.clip == key);
            if (existing != null)
            {
                if (existing.target != target) LeaveOutOpening(component.name, "Shared clip has multiple declared grab targets; explicit resolution required: " + key);
                continue;
            }
            var roots = rigged ? new[] { target } : paths.Where(p => !paths.Any(a => a != p && p.StartsWith(a + "/", StringComparison.Ordinal))).ToArray();
            if (roots.Any(p => removed.Any(a => p == a || p.StartsWith(a + "/") || a.StartsWith(p + "/"))))
                { LeaveOutOpening(component.name, "Toggle overlaps another converted moving assembly: " + key); continue; }
            string name = "rr2dvOpening" + RrOpenings.Count + "_" + Safe(key);
            string port = name + ".EXT_IN";
            ports.Add(name);
            RrOpenings.Add(new RrOpening { name = name, clip = key, target = target, hinge = ancestors[0], roots = roots, port = port,
                transitionTime = clip.length / (data.speed > 0 ? data.speed : 1f) });
            foreach (var path in roots) { removed.Add(path); noWalk.Add(path); }
            Line($"rr2dv opening source {key}: declared target {target}, animated ancestor {ancestors[0]}, {paths.Length} bound transforms, port {port}");
        }
        Cfg.CabControlObjects = removed.ToArray();
        Cfg.NoWalkParts = noWalk.ToArray();
        Cfg.SimControls = ports.ToArray();
        // These complete assemblies are now animated in the external interactables prefab.
        Cfg.LoadAnimations = Cfg.LoadAnimations.Where(a => !RrOpenings.Any(o => o.clip == a.Item1)).ToArray();
    }

    // A door, window or hatch animation that cannot be resolved is left out with a WARN naming it and why, so the rest
    // of the loco still builds (L-27: a second roof-hatch toggle whose clip does not move its declared target,
    // 2026-09-28). Never silent: the warning reaches build/review.json. Driving controls keep their hard checks.
    static void LeaveOutOpening(string component, string reason)
    {
        Warn($"rr2dv ancillary toggle '{component}' left out (not interactive; its model stays as modelled): {reason}");
    }

    static void FinishRr2dvInteriorControls()
    {
        string path = $"{carFolder}/{CarId}_interior.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            foreach (var control in root.GetComponentsInChildren<Component>(true).Where(c => c && c.GetType().Name == "LeverProxy"))
            {
                var renderers = control.GetComponentsInChildren<Renderer>(true).Where(r => r.enabled).ToArray();
                if (renderers.Length > 0) RrHighlight(control.gameObject, renderers);
                RrControlResponse(control);
            }
            StripRr2dvCutoutAxis(root);
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    // The brake cutout is a two-position valve, but CCL's control wizard gives it an absolute axis (BrakeCutoutAbsolute:
    // AnalogSetValueJoystickInputProxy) besides its toggle key, and the F4/keyboard route then drives it as a range
    // (James's game test, 2026-09-29). The two-position controls that switch correctly there (cab light, air pump,
    // dynamo, lubricator) have no absolute action in CCL's key map, so the cutout keeps only its toggle and scroll inputs.
    static void StripRr2dvCutoutAxis(GameObject root)
    {
        foreach (var feeder in root.GetComponentsInChildren<Component>(true)
                     .Where(c => c && c.GetType().Name == "InteractablePortFeederProxy" && Get<string>(c, "portId") == "brakeCutout.EXT_IN").ToList())
            foreach (var axis in feeder.GetComponents<Component>().Where(c => c && c.GetType().Name == "AnalogSetValueJoystickInputProxy").ToList())
            {
                Object.DestroyImmediate(axis);
                Line($"rr2dv brake cutout {feeder.name}: absolute axis input removed; toggle key and scroll stay (two positions, as the cab light)");
            }
    }

    static void ConfigureRrOpeningMotion()
    {
        string template = $"{carFolder}/{CarId}_template.prefab";
        var root = PrefabUtility.LoadPrefabContents(template);
        try
        {
            var sim = root.transform.Find("[sim]");
            var connections = sim.GetComponent<SimConnectionsDefinitionProxy>();
            connections.AfterImport();
            foreach (var opening in RrOpenings.Where(o => o.clickToggle))
            {
                var smooth = Child(sim, opening.name + "Motion", Vector3.zero).gameObject.AddComponent<SmoothedOutputDefinitionProxy>();
                smooth.ID = opening.name + "Motion";
                smooth.smoothTime = opening.transitionTime;
                smooth.OnValidate();
                connections.portReferenceConnections.Add(new PortReferenceConnectionProxy { portReferenceId = smooth.ID + ".CONTROL", portId = opening.port });
                connections.executionOrder.RemoveAll(p => p == smooth);
                connections.executionOrder.Add(smooth);
                Line($"rr2dv opening motion {opening.clip}: native smoothed output, response time {smooth.smoothTime:F3} s from source clip length/speed; no runtime helper");
            }
            connections.OnValidate();
            SaveRr2dvPrefab(root, template);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
    }

    static void RrHighlight(GameObject control, Renderer[] renderers)
    {
        if (renderers.Length == 0) throw new InvalidOperationException("No highlight renderers: " + control.name);
        var highlight = control.GetComponent(T("CCL.Types.Proxies.HighlightTagProxy")) ?? Add(control, "CCL.Types.Proxies.HighlightTagProxy");
        Set(highlight, "renderers", renderers.Cast<Object>().ToList());
        Line($"rr2dv highlight {control.name}: {renderers.Length} explicit same-prefab renderers");
    }

    // Coarse stepped controls where one key tap ran the whole range (James, 2026-09-29: train/independent brake 11 notches
    // over 60 deg, headlights 7 over 90 deg; the throttle's 21 felt right): the key moves one notch per press.
    static readonly string[] Rr2dvOneNotchPerPress = { "brake.EXT_IN", "indBrake.EXT_IN", "headlightDecoder.HEADLIGHTS_EXT_IN", "cabLight.EXT_IN" };

    static void RrControlResponse(Component control)
    {
        var feeder = control.GetComponents<Component>().FirstOrDefault(c => c.GetType().Name == "InteractablePortFeederProxy");
        string port = feeder ? Get<string>(feeder, "portId") : null;
        if (Rr2dvOneNotchPerPress.Contains(port))
            foreach (var keys in control.GetComponents<Component>().Where(c => c.GetType().Name == "MouseScrollKeyboardInputProxy"))
            {
                Set(keys, "onlyScrollOnce", true);
                Line($"rr2dv control response {control.name}: keyboard moves one notch per press");
            }
        // A generated whistle (Railroader has no handle) had the core's generic lever physics, heavy and slow next to an RR
        // whistle handle (James, 2026-09-29: most whistles slow, the R48's RR handle good): the same G-29 whistle role as
        // RR whistle handles (buildrecord LEVER_PHYSICS 'whistle'), then the short-lever spring rule below.
        if (port == "whistle.EXT_IN" && Cfg.Placed.Any(p => "C_" + p.Name == control.name && p.Port == port))
        {
            float travel = Get<float>(control, "jointLimitMax") - Get<float>(control, "jointLimitMin");
            Phys(control, 0, travel, 0, 50, 5, 5, 5, 0, travel * .25f, 100);
            Line($"rr2dv control response {control.name}: generated whistle given the RR whistle role physics (spring 50, damper 5, mass 5, drag 5)");
        }
        // Keep mass, spring and damping together; 0.1.2 changed mass alone and removed drag.
        if (Get<bool>(control, "useSteppedJoint"))
        {
            int notches = Get<int>(control, "notches");
            float range = Get<float>(control, "jointLimitMax") - Get<float>(control, "jointLimitMin");
            if (notches < 2 || range <= 0) throw new InvalidOperationException("Invalid stepped control: " + control.name);
            Set(control, "scrollWheelHoverScroll", range / (notches - 1));
        }
        else if (Get<bool>(control, "useSpring"))
        {
            // A spring-return control (whistle): the joint spring pulls in proportion to the angle, so a short lever keeps
            // almost no pull near closed and stops short of zero, still passing steam (RLW RPP-1 whistle, 12.9 deg, game
            // test 2026-09-28; CTRL-02). Keep the pull per fraction of travel of a ~45 deg lever at the role's spring.
            // 45 deg is an estimate of the G-29 reference travel, not a measurement: runtime-pending.
            float range = Get<float>(control, "jointLimitMax") - Get<float>(control, "jointLimitMin");
            float spring = Get<float>(control, "jointSpring");
            if (range > 0 && range < SpringReferenceTravelDeg)
            {
                float scaled = spring * SpringReferenceTravelDeg / range;
                Set(control, "jointSpring", scaled);
                Line($"rr2dv control response {control.name}: spring return over {range:F1} deg, spring {spring:F0} -> {scaled:F0} " +
                     $"(pull per fraction of travel of a {SpringReferenceTravelDeg:F0} deg lever; closed = 0 still needs the in-game check)");
                return;
            }
        }
        Line($"rr2dv control response {control.name}: role mass/damping retained; scroll follows one measured detent");
    }

    const float SpringReferenceTravelDeg = 45f;

    static void BuildRr2dvAncillaries()
    {
        if (RrOpenings.Count == 0) return;
        string path = $"{carFolder}/{CarId}_interactables.prefab";
        var root = PrefabUtility.LoadPrefabContents(path);
        try
        {
            foreach (var opening in RrOpenings) BuildRrOpening(root.transform, opening);
            SaveRr2dvPrefab(root, path);
        }
        finally { PrefabUtility.UnloadPrefabContents(root); }
        ConfigureRrOpeningMotion();
    }

    static void BuildRrOpening(Transform parent, RrOpening opening)
    {
        var clip = opening.motion = RrDirectOpeningClip(opening);
        clip.SampleAnimation(RefBody.gameObject, 0);
        var source = RefBody.Find(opening.target);
        var rs = source.GetComponentsInChildren<Renderer>(true).Where(r => r.enabled).ToArray();
        if (rs.Length == 0) throw new InvalidOperationException("Declared grab target has no visible geometry: " + opening.target);
        var bounds = rs[0].bounds;
        foreach (var r in rs) bounds.Encapsulate(r.bounds);
        Vector3 grip = bounds.center;
        var copy = Object.Instantiate(RefBody.gameObject);
        copy.name = opening.name + " source";
        try
        {
            StripScripts(copy);
            foreach (var collider in copy.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(collider);
            StripRr2dvLights(copy.transform);
            ApplyMaterials(copy, quiet: true);
            // Only this opening's own moving parts: the clip may also key other openings' parts with flat curves (M-3),
            // and those are removed from this copy below.
            var paths = AnimationUtility.GetCurveBindings(clip).Select(b => b.path).Distinct()
                .Where(p => opening.roots.Any(r => p == r || p.StartsWith(r + "/"))).ToArray();
            var mapped = paths.ToDictionary(p => p, p => copy.transform.Find(p));
            var liveTarget = copy.transform.Find(opening.target);
            // Preserve the original coordinate hierarchy and curves. Keeping only the
            // complete moving subtrees plus their transform ancestors avoids re-rooting
            // multi-bone clips, and avoids copying the stationary locomotive.
            foreach (var t in copy.GetComponentsInChildren<Transform>(true).OrderByDescending(AnimatedToggleDepth))
            {
                if (t == copy.transform) continue;
                string sourcePath = AnimationUtility.CalculateTransformPath(t, copy.transform);
                bool moving = opening.roots.Any(p => sourcePath == p || sourcePath.StartsWith(p + "/"));
                bool ancestor = opening.roots.Any(p => p.StartsWith(sourcePath + "/"));
                if (!moving && !ancestor) Object.DestroyImmediate(t.gameObject);
                else if (!moving)
                {
                    foreach (var r in t.GetComponents<Renderer>()) Object.DestroyImmediate(r);
                    foreach (var m in t.GetComponents<MeshFilter>()) Object.DestroyImmediate(m);
                }
            }
            // the same slot rules as the fixed body: an opening window's glass matches the fixed panes (M-3, 2026-09-29)
            Rr2dvFinishSlots(copy.transform, copy.transform, opening.name + " copy: ");
            Folder($"{Work}/Animators");
            var controller = AnimatorController.CreateAnimatorControllerAtPath($"{Work}/Animators/{opening.name}.controller");
            var state = controller.layers[0].stateMachine.AddState(opening.name);
            state.motion = clip; state.speed = 0;
            controller.layers[0].stateMachine.defaultState = state;
            var animation = copy.AddComponent<Animator>();
            animation.runtimeAnimatorController = controller;
            animation.cullingMode = AnimatorCullingMode.AlwaysAnimate;
            animation.applyRootMotion = false;
            var animators = new[] { animation };
            foreach (var animator in animators)
            {
                PortAnim(animator.gameObject, opening.port, .999f, 0);
                animator.transform.SetParent(parent, true);
            }
            if (!liveTarget.IsChildOf(parent)) throw new InvalidOperationException("Grab target was not moved with its complete assembly: " + opening.target);
            foreach (float phase in new[] { 0f, .25f, .5f, .75f, 1f })
            {
                clip.SampleAnimation(RefBody.gameObject, phase * clip.length);
                foreach (var animator in animators.OrderBy(a => AnimatedToggleDepth(a.transform)))
                {
                    var generated = animator.runtimeAnimatorController.animationClips.Distinct().Single();
                    generated.SampleAnimation(animator.gameObject, phase * generated.length);
                }
                foreach (var pair in mapped)
                {
                    var expected = RefBody.Find(pair.Key);
                    if (Vector3.Distance(pair.Value.position, expected.position) > .001f || Quaternion.Angle(pair.Value.rotation, expected.rotation) > .05f ||
                        Vector3.Distance(pair.Value.lossyScale, expected.lossyScale) > .001f)
                        throw new InvalidOperationException($"Opening source-pose mismatch {opening.clip}: {pair.Key}, phase {phase}");
                }
            }
            clip.SampleAnimation(RefBody.gameObject, 0);
            foreach (var animator in animators)
                animator.runtimeAnimatorController.animationClips.Distinct().Single().SampleAnimation(animator.gameObject, 0);
            var renderers = animators.SelectMany(a => a.GetComponentsInChildren<Renderer>(true)).Where(r => r.enabled).Distinct().ToArray();
            foreach (var skin in renderers.OfType<SkinnedMeshRenderer>())
                if (skin.bones.Any(b => b && !b.IsChildOf(parent))) throw new InvalidOperationException("Opening has bones outside its prefab: " + opening.clip);
            GameObject control = RrOpeningGrip(parent, opening, grip, liveTarget);
            if (opening.clickToggle)
                foreach (var animator in animators)
                    Set(animator.GetComponent(T("CCL.Types.Proxies.Ports.AnimatorPortReaderProxy")), "portId", opening.name + "Motion.OUTPUT");
            RrHighlight(control, renderers);
            Layer(control, 13, true);
            var spec = control.GetComponents<Component>().First(c => c.GetType().Name == "LeverProxy" || c.GetType().Name == "PullerProxy" || c.GetType().Name == "ButtonProxy");
            var area = (Component)new SerializedObject(spec).FindProperty("nonVrStaticInteractionArea").objectReferenceValue;
            area.transform.position = bounds.center;
            area.transform.rotation = Quaternion.identity;
            var box = area.GetComponent<BoxCollider>();
            box.center = Vector3.zero;
            box.size = Vector3.Max(bounds.size, Vector3.one * .14f);
            box.isTrigger = true;
            if (spec.GetType().Name != "ButtonProxy") Add(control, "CCL.Types.Proxies.Weather.OpenableControlProxy");
            Line($"rr2dv opening verified {opening.clip}: {paths.Length} transforms at 5 phases, complete visual assembly, declared-target grip {V(grip)}, {spec.GetType().Name}; {opening.port}");
        }
        finally { if (!copy.transform.IsChildOf(parent)) Object.DestroyImmediate(copy); clip.SampleAnimation(RefBody.gameObject, 0); }
    }

    static GameObject RrOpeningGrip(Transform parent, RrOpening opening, Vector3 grip, Transform liveTarget)
    {
        var clip = opening.motion ?? Clip(opening.clip);
        var hinge = RefBody.Find(opening.hinge);
        var target = RefBody.Find(opening.target);
        clip.SampleAnimation(RefBody.gameObject, 0);
        Vector3 p0 = hinge.position;
        Quaternion q0 = hinge.rotation;
        Vector3 targetPosition = hinge.InverseTransformPoint(target.position);
        Quaternion targetRotation = Quaternion.Inverse(q0) * target.rotation;
        clip.SampleAnimation(RefBody.gameObject, clip.length);
        Vector3 p1 = hinge.position;
        Quaternion q1 = hinge.rotation;
        float angle = Quaternion.Angle(q0, q1);
        bool rotates = angle > .5f && angle < 179.9f && Vector3.Distance(p0, p1) < .001f;
        bool slides = angle < .05f && Vector3.Distance(p0, p1) > .01f;
        foreach (float phase in new[] { .25f, .5f, .75f, 1f })
        {
            clip.SampleAnimation(RefBody.gameObject, phase * clip.length);
            if (Quaternion.Angle(hinge.rotation, Quaternion.Slerp(q0, q1, phase)) > .05f ||
                Vector3.Distance(hinge.position, Vector3.Lerp(p0, p1, phase)) > .001f ||
                Vector3.Distance(hinge.InverseTransformPoint(target.position), targetPosition) > .001f ||
                Quaternion.Angle(Quaternion.Inverse(hinge.rotation) * target.rotation, targetRotation) > .05f)
                { rotates = false; slides = false; }
        }
        clip.SampleAnimation(RefBody.gameObject, 0);
        GameObject result;
        if (rotates)
        {
            result = RrLever(parent, new RrLeverCfg { Path = opening.hinge, AnimKey = opening.clip, Port = opening.port,
                Hidden = true, Toggle = true, Grip = grip, GripSize = Vector3.one * .08f,
                Phys = (spec, a) => Phys(spec, 0, a, 11, 50, 10, 1, 0, 0, 1, 0) });
            RrControlResponse(result.GetComponent(T("CCL.Types.Proxies.Controls.LeverProxy")));
        }
        else if (slides)
        {
            result = RrPuller(parent, new PullerCfg { Path = opening.hinge, AnimKey = opening.clip, Port = opening.port,
                Name = opening.name, Grip = grip, GripSize = Vector3.one * .08f });
            var spec = result.GetComponent(T("CCL.Types.Proxies.Controls.PullerProxy"));
            // Native puller notches count intervals (unlike lever notches), and scroll is normalized.
            Set(spec, "useSteppedPuller", true); Set(spec, "notches", 10);
            Set(spec, "scrollWheelHoverScroll", .1f);
        }
        else
        {
            opening.clickToggle = true;
            // Compound/eased motion keeps the exact clip; the button and its grip ride on
            // the declared source target instead of pretending it is a single-axis lever.
            var c = Child(liveTarget, "C_" + opening.name, liveTarget.InverseTransformPoint(grip));
            var scale = liveTarget.lossyScale;
            if (!AnimatedToggleFinite(scale) || Mathf.Abs(scale.x) < .000001f || Mathf.Abs(scale.y) < .000001f || Mathf.Abs(scale.z) < .000001f)
                throw new InvalidOperationException("Declared grip target has invalid scale: " + opening.target);
            c.localScale = new Vector3(1f / scale.x, 1f / scale.y, 1f / scale.z);
            if (Vector3.Distance(c.lossyScale, Vector3.one) > .001f)
                throw new InvalidOperationException("Cannot preserve physical grip size under the target hierarchy: " + opening.target);
            var col = Child(c, "collider", Vector3.zero);
            col.gameObject.AddComponent<BoxCollider>().size = Vector3.one * .08f;
            var spec = Add(c.gameObject, "CCL.Types.Proxies.Controls.ButtonProxy");
            Set(spec, "createRigidbody", false); Set(spec, "useJoints", false);
            Set(spec, "isToggle", true); Set(spec, "isTogglingBack", false);
            Set(spec, "pushLocalOffset", Vector3.zero); Set(spec, "disableTouchUse", false);
            Interactable(c, col, spec, opening.port, -1, false);
            result = c.gameObject;
        }
        if (!result) throw new InvalidOperationException("Opening control was not created: " + opening.clip);
        result.name = "C_" + opening.name;
        return result;
    }
}
