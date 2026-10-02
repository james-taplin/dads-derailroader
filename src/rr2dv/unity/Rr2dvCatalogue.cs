using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using CCL.Types;
using CCL.Types.Catalog;
using DVLangHelper.Data;
using UnityEditor;
using UnityEngine;

// Editor-only. Python imports only the selected engine/tender assets into the run project.
// CCL exports the pack root and its references; this attaches every livery of each selected car.
public static class Rr2dvCatalogue
{
    public const string InputPath = "Assets/Rr2dv/CatalogueInput.json";
    const string Root = "Assets/RRStockCatalogue";
    [Serializable] public class Term { public string key, text; }
    [Serializable] public class Page { public string sourceId, carId, assetName, kind, consist; public Term[] terms; }
    [Serializable] public class Input { public int schema; public string locoSourceId; public Page[] pages; }

    public static Input ReadInput()
    {
        if (!File.Exists(InputPath)) return null; // synthetic/non-stock build
        var input = JsonUtility.FromJson<Input>(File.ReadAllText(InputPath));
        if (input == null || input.schema != 1 || input.pages == null || input.pages.Length == 0)
            throw new InvalidDataException("Unsupported or empty catalogue selection");
        return input;
    }

    public static void Attach(CustomCarPack pack, Input input, Action<string> log = null)
    {
        if (input == null) return;
        if (!pack || pack.Cars == null || pack.Cars.Any(c => !c))
            throw new InvalidDataException("Catalogue attachment needs the completed car pack");
        var ids = input.pages.Select(p => p.carId).ToArray();
        if (ids.Distinct().Count() != ids.Length || !new HashSet<string>(pack.Cars.Select(c => c.id)).SetEquals(ids))
            throw new InvalidDataException("Catalogue selection differs from the exported car types");
        var targets = new List<Tuple<CustomCarVariant, CatalogPage, Sprite>>();
        var terms = new List<Term>();
        foreach (var selected in input.pages)
        {
            string folder = Root + "/" + selected.sourceId + "/" + selected.sourceId;
            var page = AssetDatabase.LoadAssetAtPath<CatalogPage>(folder + "-catalogue.asset");
            var icon = AssetDatabase.LoadAssetAtPath<Sprite>(folder + "-icon.png");
            if (!page || !icon) throw new InvalidDataException("Missing catalogue page or icon for " + selected.sourceId);
            page.AfterImport();
            if (!page.DiagramLayout || page.name != selected.assetName || page.ConsistUnits != selected.consist ||
                (page.Type == VehicleType.Tender) != (selected.kind == "tender"))
                throw new InvalidDataException("Catalogue page identity or diagram mismatch for " + selected.sourceId);
            var car = pack.Cars.Single(c => c.id == selected.carId);
            if (car.liveries == null || car.liveries.Count == 0 || car.liveries.Any(v => !v))
                throw new InvalidDataException("No valid liveries to attach the page to for " + car.id);
            foreach (var variant in car.liveries)
                targets.Add(Tuple.Create(variant, page, icon));
            terms.AddRange(selected.terms ?? new Term[0]);
        }
        if (targets.Select(t => t.Item1).Distinct().Count() != targets.Count)
            throw new InvalidDataException("Catalogue engine and tender must have distinct livery assets");
        if (terms.Any(t => string.IsNullOrEmpty(t.key)) || terms.Select(t => t.key).Distinct().Count() != terms.Count)
            throw new InvalidDataException("Empty or duplicate catalogue translation key");

        var extras = pack.ExtraTranslations;
        if (!extras)
        {
            string path = Path.GetDirectoryName(AssetDatabase.GetAssetPath(pack)).Replace('\\', '/') + "/RR-catalogue-translations.asset";
            extras = AssetDatabase.LoadAssetAtPath<ExtraTranslations>(path);
            if (!extras)
            {
                extras = ScriptableObject.CreateInstance<ExtraTranslations>();
                extras.Terms = new ExtraTranslations.TermData[0];
                AssetDatabase.CreateAsset(extras, path);
            }
            pack.ExtraTranslations = extras;
        }
        extras.AfterImport();
        var merged = (extras.Terms ?? new ExtraTranslations.TermData[0]).ToDictionary(t => t.Term, t => t);
        var selectedKeys = new HashSet<string>(terms.Select(t => t.key));
        // Remove only old library terms unrelated to this pack, preserving unrelated user translations.
        foreach (var key in merged.Keys.Where(k => k.StartsWith("rrstock/catalogue/", StringComparison.Ordinal) && !selectedKeys.Contains(k)).ToArray())
            merged.Remove(key);
        foreach (var term in terms)
        {
            var addition = TranslationData.Default(term.text);
            if (!merged.ContainsKey(term.key))
                merged.Add(term.key, new ExtraTranslations.TermData { Term = term.key, Data = addition });
            else
            {
                var data = merged[term.key].Data;
                if (data == null) data = merged[term.key].Data = new TranslationData();
                if (data.Items == null) data.Items = new List<TranslationItem>();
                foreach (var item in addition.Items)
                {
                    var existing = data.Items.FirstOrDefault(i => i.Language == item.Language);
                    if (existing == null) data.Items.Add(new TranslationItem(item.Language, item.Value));
                    else existing.Value = item.Value;
                }
            }
        }
        extras.Terms = merged.Values.OrderBy(t => t.Term, StringComparer.Ordinal).ToArray();
        extras.OnValidate();
        EditorUtility.SetDirty(extras);
        foreach (var target in targets)
        {
            target.Item1.CatalogPage = target.Item2;
            target.Item1.icon = target.Item3;
            EditorUtility.SetDirty(target.Item1);
            if (log != null) log("rr2dv catalogue: " + target.Item1.id + " -> " + target.Item2.name + " (" + target.Item2.ConsistUnits + ")");
        }
        pack.OnValidate();
        EditorUtility.SetDirty(pack);
        AssetDatabase.SaveAssets();
        if (log != null) log("rr2dv catalogue: " + input.pages.Length + " selected page(s), " + targets.Count + " livery reference(s), " + terms.Count + " selected text keys");
    }
}
