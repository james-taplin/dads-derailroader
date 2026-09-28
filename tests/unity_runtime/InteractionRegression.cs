using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

public static partial class CclLocoBuild
{
    public static void InteractionRegression()
    {
        const string folder = "Assets/Rr2dvInteractionRegression";
        try
        {
            if (AssetDatabase.IsValidFolder(folder)) AssetDatabase.DeleteAsset(folder);
            Folder(folder);
            var source = new GameObject("Source");
            var body = Child(source.transform, "Body", Vector3.zero);
            // Same leaf names; the first clip binding is deliberately not the grab target.
            var decoy = Child(body, "Decoy", Vector3.zero);
            var wanted = Child(body, "Wanted", Vector3.up);
            foreach (var node in new[] { decoy, wanted })
            {
                var mesh = GameObject.CreatePrimitive(PrimitiveType.Cube);
                mesh.name = "Handle"; mesh.transform.SetParent(node, false);
                mesh.transform.localScale = Vector3.one * .1f;
            }
            var clip = new AnimationClip { name = "LinkedWindow", frameRate = 60 };
            clip.SetCurve("Body/Decoy", typeof(Transform), "localPosition.z", AnimationCurve.Linear(0, 0, 1, .1f));
            clip.SetCurve("Body/Wanted", typeof(Transform), "localPosition.x", AnimationCurve.Linear(0, 0, 1, .3f));
            AssetDatabase.CreateAsset(clip, folder + "/source.anim");
            Cfg = new LocoConfig { CarId = "Synthetic", Work = folder,
                Components = new List<Comp> { new Comp { kind = "ToggleAnimation", name = "Window",
                    extra = "{\"animation\":{\"clipName\":\"Window\"},\"targetColliderObject\":{\"path\":[\"Body\",\"Wanted\",\"Handle\"]},\"enabled\":true}" } },
                AnimationMap = new Dictionary<string, string> { { "Window", folder + "/source.anim" } } };
            refBody = source.transform;
            validatedClips.Clear();
            matMap = new Dictionary<Material, Material>();
            PrepareRr2dvInteractions();
            if (RrOpenings.Single().hinge != "Body/Wanted") throw new Exception("Selected the first bound descendant instead of the declared target ancestor");
            var output = new GameObject("External");
            BuildRrOpening(output.transform, RrOpenings.Single());
            if (!output.GetComponentsInChildren<Component>(true).Any(c => c.GetType().Name == "PullerProxy"))
                throw new Exception("Linear declared target did not become a puller");
            var puller = output.GetComponentsInChildren<Component>(true).Single(c => c.GetType().Name == "PullerProxy");
            if (!Get<bool>(puller, "useSteppedPuller") || Mathf.Abs(Get<float>(puller, "scrollWheelHoverScroll") * Get<int>(puller, "notches") - 1) > .0001f)
                throw new Exception("Puller scroll is not exactly one normalized detent");
            string prefab = folder + "/external.prefab";
            SaveRr2dvPrefab(output, prefab);
            Object.DestroyImmediate(output);
            var loaded = PrefabUtility.LoadPrefabContents(prefab);
            try
            {
                var tag = loaded.GetComponentsInChildren<Component>(true).Single(c => c.GetType().Name == "HighlightTagProxy");
                var renderers = new SerializedObject(tag).FindProperty("renderers");
                if (renderers.arraySize != 2) throw new Exception("Lost part of the linked highlight assembly");
                for (int i = 0; i < renderers.arraySize; i++)
                {
                    var renderer = renderers.GetArrayElementAtIndex(i).objectReferenceValue as Renderer;
                    if (!renderer || !renderer.transform.IsChildOf(loaded.transform)) throw new Exception("Highlight reference escaped the saved prefab");
                }
            }
            finally { PrefabUtility.UnloadPrefabContents(loaded); }
            clip.SetCurve("Body/Wanted", typeof(Transform), "localPosition.x", AnimationCurve.EaseInOut(0, 0, 1, .3f));
            RrOpenings[0].name += "Eased";
            output = new GameObject("EasedExternal");
            BuildRrOpening(output.transform, RrOpenings.Single());
            if (!output.GetComponentsInChildren<Component>(true).Any(c => c.GetType().Name == "PullerProxy"))
                throw new Exception("Eased single-axis motion lost direct manipulation");
            Object.DestroyImmediate(output);
            clip.SetCurve("Body/Wanted", typeof(Transform), "localPosition.y", AnimationCurve.EaseInOut(0, 1, .5f, 1.2f));
            RrOpenings[0].name += "Compound";
            output = new GameObject("CompoundExternal");
            BuildRrOpening(output.transform, RrOpenings.Single());
            var button = output.GetComponentsInChildren<Component>(true).Single(c => c.GetType().Name == "ButtonProxy");
            if (Vector3.Distance(button.transform.lossyScale, Vector3.one) > .001f)
                throw new Exception("Small source target shrank the physical grip");
            if (!RrOpenings[0].clickToggle) throw new Exception("Compound source motion was forced into a linear joint");
            Object.DestroyImmediate(output);
            Cfg.Components[0].extra = Cfg.Components[0].extra.Replace("Wanted", "Missing");
            bool blocked = false;
            try { PrepareRr2dvInteractions(); }
            catch (InvalidOperationException) { blocked = true; }
            if (!blocked) throw new Exception("Missing declared target was silently ignored");
            Object.DestroyImmediate(source);
            File.WriteAllText(Path.Combine(Application.dataPath, "../interaction-regression.txt"),
                "declared-target-over-first-binding\ncomplete-multipart-source-poses\nstepped-puller-scroll\nsaved-same-prefab-highlights\neased-direct-and-compound-click\nphysical-grip-scale\nunresolved-target-blocked\n");
            EditorApplication.Exit(0);
        }
        catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
    }
}
