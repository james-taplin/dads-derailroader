using System;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

// Synthetic real-Unity regression: no game assets or source scripts are required.
public static class PrepRegression
{
    static object Call(string method, params object[] args)
    {
        try { return typeof(Rr2dvBuild).GetMethod(method, BindingFlags.Static | BindingFlags.NonPublic).Invoke(null, args); }
        catch (TargetInvocationException e) { throw e.InnerException; }
    }
    static void Require(bool condition, string why) { if (!condition) throw new Exception(why); }
    public static void Run()
    {
        try
        {
            const string source = "Assets/Missing.prefab";
            var root = GameObject.CreatePrimitive(PrimitiveType.Cube);
            root.name = "Synthetic";
            root.AddComponent<AudioSource>();
            var child = new GameObject("inactive valid child");
            child.transform.SetParent(root.transform, false);
            child.AddComponent<Light>();
            child.SetActive(false);
            PrefabUtility.SaveAsPrefabAsset(root, source);
            Object.DestroyImmediate(root);
            var yaml = File.ReadAllText(source).Replace("\r\n", "\n");
            var rootName = AssetDatabase.LoadAssetAtPath<GameObject>(source).name;
            // Unity does not guarantee that the root GameObject is the first YAML object.
            var rootBlock = System.Text.RegularExpressions.Regex.Matches(yaml,
                @"(?ms)^--- !u!1 &(-?\d+)\nGameObject:\n.*?(?=^---|\z)")
                .Cast<System.Text.RegularExpressions.Match>()
                .Single(m => System.Text.RegularExpressions.Regex.IsMatch(m.Value,
                    @"(?m)^  m_Name: " + System.Text.RegularExpressions.Regex.Escape(rootName) + "$"));
            int componentOffset = rootBlock.Value.IndexOf("  m_Component:\n", StringComparison.Ordinal);
            int at = componentOffset < 0 ? -1 : rootBlock.Index + componentOffset;
            Require(at >= 0, "fixture did not serialize as YAML");
            yaml = yaml.Insert(at + "  m_Component:\n".Length, "  - component: {fileID: 114999}\n");
            yaml += "\n--- !u!114 &114999\nMonoBehaviour:\n  m_ObjectHideFlags: 0\n  m_GameObject: {fileID: 0}\n  m_Enabled: 1\n  m_EditorHideFlags: 0\n  m_Script: {fileID: 11500000, guid: deadbeefdeadbeefdeadbeefdeadbeef, type: 3}\n  m_Name: \n  m_EditorClassIdentifier: \n";
            // Attach the missing component to the actual root GameObject ID, independent of Unity's generated IDs.
            var gameId = rootBlock.Groups[1].Value;
            yaml = yaml.Replace("m_GameObject: {fileID: 0}", "m_GameObject: {fileID: " + gameId + "}");
            File.WriteAllText(source, yaml);
            AssetDatabase.ImportAsset(source, ImportAssetOptions.ForceUpdate);
            var instance = (GameObject)PrefabUtility.InstantiatePrefab(AssetDatabase.LoadAssetAtPath<GameObject>(source));
            PrefabUtility.UnpackPrefabInstance(instance, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            Require(instance.GetComponents<Component>().Any(c => c == null), "fixture has no missing script");
            bool failed = false;
            try { Call("SaveChecked", instance, "Assets/MustFail.prefab"); }
            catch (InvalidOperationException e) { failed = e.Message.Contains("prefab save failed"); }
            finally { Object.DestroyImmediate(instance); }
            Require(failed, "unchecked or unexpected prefab save failure");
            Require(!File.Exists("Assets/MustFail.prefab"), "failed save unexpectedly produced a prefab");
            var stripped = (Rr2dvBuild.Stripped)Call("StripAudio", source);
            Require(stripped.audioSources == 1, "audio removal count");
            Require(stripped.missingScripts.Sum(s => s.count) == 1, "missing script removal count");
            Call("MakeComposite", new Rr2dvBuild.Composite { vehicle = "test", source = source, target = "Assets/Generated/Test.prefab", parts = new Rr2dvBuild.Part[0] });
            var clean = PrefabUtility.LoadPrefabContents("Assets/Generated/Test.prefab");
            try
            {
                Require(clean.GetComponent<BoxCollider>() && clean.GetComponent<MeshRenderer>(), "valid components lost");
                Require(clean.GetComponentsInChildren<Light>(true).Length == 1, "inactive child lost");
                Require(clean.GetComponentsInChildren<AudioSource>(true).Length == 0, "audio retained");
                Require(clean.GetComponentsInChildren<Transform>(true).All(t => t.GetComponents<Component>().All(c => c != null)), "missing script retained");
            }
            finally { PrefabUtility.UnloadPrefabContents(clean); }
            File.WriteAllText("regression-passed.json", "{\"failedSaveCaught\":true,\"reloadVerified\":true,\"validComponentsRetained\":true}");
            EditorApplication.Exit(0);
        }
        catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
    }
}

// Stand-in only for the downstream builder; reaching it in the failure test is itself a regression.
public static class CclLocoBuild
{
    public static void RunRr2dvRecord() { File.WriteAllText("unexpected-downstream.txt", "called"); EditorApplication.Exit(9); }
}
