using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using CCL.Types;
using CCL.Types.Catalog;
using DVLangHelper.Data;
using UnityEditor;
using UnityEngine;
using Object = UnityEngine.Object;

// Unity 2019.4 + real CCL 3.1.9. Test the same root-only dependency export that
// CCL uses, with several unrelated page sets present in the authoring project.
public static class CatalogueRegression
{
    static void Require(bool condition, string message) { if (!condition) throw new Exception(message); }
    public static void Run()
    {
        string output = Environment.GetEnvironmentVariable("CATALOGUE_TEST_OUT");
        try
        {
            Directory.CreateDirectory(output);
            var results = new List<string>();
            foreach (var id in new[] { "ls-2102-f71", "ls-282-k28t", "ls-480-c40" })
            {
                var input = JsonUtility.FromJson<Rr2dvCatalogue.Input>(File.ReadAllText("Assets/Rr2dv/selection-" + id + ".json"));
                string folder = "Assets/CatalogueRegression/" + id;
                Directory.CreateDirectory(folder); AssetDatabase.Refresh();
                var pack = ScriptableObject.CreateInstance<CustomCarPack>();
                pack.PackId = id; pack.PackName = id;
                AssetDatabase.CreateAsset(pack, folder + "/pack.asset");
                var cars = new List<CustomCarType>();
                foreach (var page in input.pages)
                {
                    var car = ScriptableObject.CreateInstance<CustomCarType>();
                    car.id = page.carId; car.liveries = new List<CustomCarVariant>();
                    AssetDatabase.CreateAsset(car, folder + "/" + page.sourceId + "-type.asset");
                    // Multiple liveries must all acquire the correct single shared page.
                    foreach (var suffix in new[] { "default", "alternate" })
                    {
                        var livery = ScriptableObject.CreateInstance<CustomCarVariant>();
                        livery.id = page.carId + "_" + suffix; livery.parentType = car;
                        AssetDatabase.CreateAsset(livery, folder + "/" + page.sourceId + "-" + suffix + ".asset");
                        car.liveries.Add(livery);
                    }
                    EditorUtility.SetDirty(car); cars.Add(car);
                }
                pack.Cars = cars.ToArray();
                var extras = ScriptableObject.CreateInstance<ExtraTranslations>();
                extras.Terms = new[] {
                    new ExtraTranslations.TermData { Term = "existing/test", Data = TranslationData.Default("Preserved") },
                    new ExtraTranslations.TermData { Term = "rrstock/catalogue/unrelated/old", Data = TranslationData.Default("Must not ship") }
                };
                extras.OnValidate(); AssetDatabase.CreateAsset(extras, folder + "/translations.asset");
                pack.ExtraTranslations = extras;
                Rr2dvCatalogue.Attach(pack, input);
                int termCount = pack.ExtraTranslations.Terms.Length;
                Rr2dvCatalogue.Attach(pack, input);
                Require(pack.ExtraTranslations.Terms.Length == termCount, "Repeated attachment duplicated translations");
                Require(pack.ExtraTranslations.Terms.Any(t => t.Term == "existing/test"), "User translations were removed");
                Require(!pack.ExtraTranslations.Terms.Any(t => t.Term.Contains("/unrelated/")), "Foreign catalogue terms were retained");
                var savedIds = input.pages.Select(p => p.carId).ToArray();
                input.pages[0].carId = "wrong-car";
                bool rejected = false;
                try { Rr2dvCatalogue.Attach(pack, input); } catch (InvalidDataException) { rejected = true; }
                Require(rejected, "Wrong car ID was accepted"); input.pages[0].carId = savedIds[0];
                string bundles = Path.Combine(output, id); Directory.CreateDirectory(bundles);
                var manifest = BuildPipeline.BuildAssetBundles(bundles, new[] {
                    new AssetBundleBuild { assetBundleName = "catalogue-test", assetNames = new[] { folder + "/pack.asset" } }
                }, BuildAssetBundleOptions.ForceRebuildAssetBundle, BuildTarget.StandaloneWindows64);
                Require(manifest != null, "Bundle build failed");
                var bundle = AssetBundle.LoadFromFile(Path.Combine(bundles, "catalogue-test"));
                Require(bundle != null, "Bundle could not be reloaded");
                try
                {
                    var loaded = bundle.LoadAllAssets<CustomCarPack>().Single();
                    var collect = typeof(Rr2dvAudit).GetMethod("CollectObjects", BindingFlags.NonPublic | BindingFlags.Static);
                    var errors = new List<string>();
                    var all = (List<Object>)collect.Invoke(null, new object[] { new Object[] { loaded }, errors });
                    var audit = new Rr2dvAudit.Input {
                        cataloguePages = input.pages.Select(p => new Rr2dvAudit.CataloguePage { sourceId=p.sourceId, carId=p.carId, assetName=p.assetName, consist=p.consist }).ToArray(),
                        catalogueTermKeys = input.pages.SelectMany(p => p.terms).Select(t => t.key).ToArray()
                    };
                    var result = new Rr2dvAudit.Output();
                    Rr2dvAudit.CheckCatalogue(audit, all, result, errors);
                    Require(errors.Count==0, "Exported catalogue audit failed: " + string.Join("; ", errors));
                    Require(result.cataloguePages.Length==input.pages.Length, "Unrelated pages exported");
                    Require(result.catalogueLiveries.Length==input.pages.Length*2, "Not every livery survived export");
                    // The runtime deserializer must retain the native diagram and page fields.
                    loaded.AfterImport();
                    Require(loaded.Cars.SelectMany(c => c.liveries).All(v => v.CatalogPage && v.CatalogPage.DiagramLayout && v.icon), "Runtime page/icon/diagram references were lost");
                    var foreign = ScriptableObject.CreateInstance<CatalogPage>(); foreign.name="unrelated-catalogue";
                    all.Add(foreign); errors.Clear();
                    Rr2dvAudit.CheckCatalogue(audit, all, new Rr2dvAudit.Output(), errors);
                    Require(errors.Any(e => e.Contains("exported pages differ")), "Audit accepted an unrelated page");
                    all.Remove(foreign); Object.DestroyImmediate(foreign);
                    var variant = loaded.Cars[0].liveries[0]; variant.CatalogPage = null; errors.Clear();
                    Rr2dvAudit.CheckCatalogue(audit, all, new Rr2dvAudit.Output(), errors);
                    Require(errors.Any(e => e.Contains("wrong page")), "Audit accepted a missing livery page");
                    results.Add(id + ": " + result.cataloguePages.Length + " pages, " + result.catalogueLiveries.Length + " liveries, only selected keys");
                }
                finally { bundle.Unload(true); }
            }
            File.WriteAllText(Path.Combine(output,"checks.txt"), string.Join("\n",results));
            File.WriteAllText(Path.Combine(output,"result.json"), "{\"passed\":true,\"packs\":3,\"rootOnlyExport\":true,\"unrelatedPagesRejected\":true,\"missingLiveryPagesRejected\":true}");
            EditorApplication.Exit(0);
        }
        catch (Exception e)
        {
            Debug.LogException(e);
            File.WriteAllText(Path.Combine(output,"result.json"), "{\"passed\":false}");
            EditorApplication.Exit(1);
        }
    }
}
