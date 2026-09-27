using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Object = UnityEngine.Object;

// Synthetic end geometry: no vehicle names, assets or tuned vehicle dimensions.
public static partial class CclLocoBuild
{
    public static void EndBeamRegression()
    {
        var checks = new List<string>();
        var prior = Cfg;
        try
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            foreach (int dir in new[] { 1, -1 })
            {
                Cfg = new LocoConfig { RrEndFront = 3.1f, RrEndRear = -3.1f };
                var body = new GameObject("end geometry");
                BeamTestBox(body, "low beam", new Vector3(0, .4f, dir * 3f), new Vector3(1.5f, .16f, .2f));
                BeamTestBox(body, "coupler head", new Vector3(0, .42f, dir * 3.3f), new Vector3(.5f, .3f, .3f));
                BeamTestBox(body, "truck crossmember", new Vector3(0, .7f, dir * 2.9f), new Vector3(1.5f, .2f, .2f));
                string detail;
                float z = EndBeam(body, dir, out detail);
                BeamTestAssert(Mathf.Abs(z - dir * 3.1f) < .002f && detail.Contains("automatic height search"), "low face with narrow hardware, end " + dir, checks);
                BeamTestAssert(Mathf.Abs(EndBeam(body, dir, out detail) - z) < .00001f, "repeatable end " + dir, checks);
                Cfg.EndBeamProbeHeight = new Vector2(.85f, 1.05f);
                BeamTestReject(body, dir, "explicit reviewed band was not changed", checks);
                Cfg.EndBeamProbeHeight = null;
                BeamTestBox(body, "tank end above hook height", new Vector3(0, 1.4f, dir * 3.2f), new Vector3(1.5f, .2f, .2f));
                BeamTestAssert(Mathf.Abs(EndBeam(body, dir, out detail) - z) < .00001f, "higher tank end ignored, end " + dir, checks);
                Object.DestroyImmediate(body);
            }
            Cfg = new LocoConfig { RrEndFront = 3.1f };
            var sparse = new GameObject("only narrow hardware");
            BeamTestBox(sparse, "head", new Vector3(0, .4f, 3), new Vector3(.3f, .2f, .2f));
            BeamTestReject(sparse, 1, "no broad transverse face", checks);
            Object.DestroyImmediate(sparse);

            var distant = new GameObject("interior bulkhead");
            BeamTestBox(distant, "bulkhead", new Vector3(0, .4f, 2), new Vector3(1.5f, .2f, .2f));
            BeamTestReject(distant, 1, "no broad transverse face", checks);
            Object.DestroyImmediate(distant);

            var seam = new GameObject("face crosses rounding boundary");
            BeamTestBox(seam, "left beam", new Vector3(-.4f, .4f, 3.004f), new Vector3(.8f, .16f, .2f));
            BeamTestBox(seam, "right beam", new Vector3(.4f, .4f, 3.008f), new Vector3(.8f, .16f, .2f));
            string evidence;
            float measured = EndBeam(seam, 1, out evidence);
            BeamTestAssert(measured > 3.103f && measured < 3.109f, "split depth bin treated as one measured face", checks);
            Object.DestroyImmediate(seam);

            var stock = new GameObject("ordinary hook-height beam");
            BeamTestBox(stock, "beam", new Vector3(0, .95f, 3), new Vector3(1.5f, .3f, .2f));
            BeamTestAssert(Mathf.Abs(EndBeam(stock, 1, out evidence) - 3.1f) < .002f && !evidence.Contains("automatic"), "successful default band preserved", checks);
            Object.DestroyImmediate(stock);
            File.WriteAllLines(Environment.GetEnvironmentVariable("RR2DV_BEAM_TEST_REPORT"), checks);
            EditorApplication.Exit(0);
        }
        catch (Exception e) { Debug.LogException(e); EditorApplication.Exit(1); }
        finally { Cfg = prior; }
    }

    static void BeamTestBox(GameObject body, string name, Vector3 position, Vector3 size)
    {
        var box = GameObject.CreatePrimitive(PrimitiveType.Cube);
        box.name = name;
        box.transform.SetParent(body.transform, false);
        box.transform.localPosition = position;
        box.transform.localScale = size;
    }
    static void BeamTestAssert(bool ok, string name, List<string> checks)
    {
        if (!ok) throw new Exception(name);
        checks.Add("PASS " + name);
    }
    static void BeamTestReject(GameObject body, int dir, string expected, List<string> checks)
    {
        try { string detail; EndBeam(body, dir, out detail); }
        catch (InvalidOperationException e)
        {
            BeamTestAssert(e.Message.Contains(expected), expected + ": " + e.Message, checks);
            return;
        }
        throw new Exception("Expected rejection: " + expected);
    }
}
