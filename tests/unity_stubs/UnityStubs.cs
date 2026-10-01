// Compile-only stand-ins for the Unity 2019.4 editor API our app scripts use (tests/test_csharp_api.py). Signatures
// follow the Unity 2019.4 scripting reference; bodies do nothing. This is never copied into a Unity project.
#pragma warning disable 0067, 0649, 0169
using System;
using System.Collections;
using System.Collections.Generic;

namespace UnityEngine
{
    public class Object
    {
        public string name;
        public static implicit operator bool(Object o) => o != null;
        public static void DestroyImmediate(Object o) { }
        public static void DestroyImmediate(Object o, bool allowDestroyingAssets) { }
    }
    public class Component : Object
    {
        public Transform transform; public GameObject gameObject;
        public T[] GetComponents<T>() => null;
        public T GetComponent<T>() => default(T);
        public T[] GetComponentsInChildren<T>(bool includeInactive) => null;
        public T[] GetComponentsInChildren<T>() => null;
    }
    public class Behaviour : Component { public bool enabled; }
    public class MonoBehaviour : Behaviour { }
    public class ScriptableObject : Object { }
    public class GameObject : Object
    {
        public T[] GetComponents<T>() => null;
        public GameObject() { } public GameObject(string name) { }
        public Transform transform; public bool activeInHierarchy;
        public SceneManagement.Scene scene;
        public T AddComponent<T>() where T : Component => default(T);
        public static GameObject CreatePrimitive(PrimitiveType t) => null;
        public T GetComponent<T>() => default(T);
        public T[] GetComponentsInChildren<T>(bool includeInactive) => null;
    }
    public class Transform : Component, IEnumerable
    {
        public Vector3 position, localPosition, lossyScale, localScale, eulerAngles;
        public Quaternion rotation, localRotation; public Transform parent;
        public Transform Find(string n) => null;
        public bool IsChildOf(Transform t) => false;
        public void LookAt(Vector3 p) { }
        public Vector3 TransformPoint(Vector3 p) => p;
        public Vector3 InverseTransformPoint(Vector3 p) => p;
        public void SetParent(Transform p, bool worldPositionStays) { }
        public IEnumerator GetEnumerator() => null;
    }
    public struct Vector2 { public float x, y; public Vector2(float x, float y) { this.x = x; this.y = y; } public float magnitude => 0; }
    public struct Vector3
    {
        public float x, y, z; public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public static Vector3 zero, one, forward, up, down, left, right, back;
        public static Vector3 operator -(Vector3 a, Vector3 b) => a;
        public static Vector3 operator +(Vector3 a, Vector3 b) => a;
        public static Vector3 operator -(Vector3 a) => a;
        public static Vector3 operator *(Vector3 a, float f) => a;
        public static Vector3 operator *(float f, Vector3 a) => a;
        public static Vector3 operator /(Vector3 a, float f) => a;
        public Vector3 normalized => this; public float magnitude => 0; public float sqrMagnitude => 0;
        public static Vector3 Cross(Vector3 a, Vector3 b) => a;
        public static float Dot(Vector3 a, Vector3 b) => 0;
        public static float Distance(Vector3 a, Vector3 b) => 0;
        public static Vector3 Scale(Vector3 a, Vector3 b) => a;
    }
    public struct Quaternion
    {
        public float x, y, z, w; public Quaternion(float x, float y, float z, float w) { this.x = x; this.y = y; this.z = z; this.w = w; }
        public static Quaternion identity;
        public static Quaternion Euler(float x, float y, float z) => identity;
        public static float Angle(Quaternion a, Quaternion b) => 0;
        public static Quaternion operator *(Quaternion a, Quaternion b) => a;
        public static Vector3 operator *(Quaternion a, Vector3 v) => v;
        public static Quaternion Inverse(Quaternion q) => q;
    }
    public struct Bounds { public Bounds(Vector3 c, Vector3 s) { center = c; min = c; max = c; } public Vector3 center, min, max; public void Encapsulate(Vector3 p) { } public void Encapsulate(Bounds b) { } }
    public struct LOD { public float screenRelativeTransitionHeight; public Renderer[] renderers; }
    public class LODGroup : Component { public LOD[] GetLODs() => null; }
    public class Renderer : Component { public bool enabled; public Bounds bounds; public Material[] sharedMaterials; public Material sharedMaterial; }
    public class MeshRenderer : Renderer { }
    public class SkinnedMeshRenderer : Renderer { public Mesh sharedMesh; }
    public class MeshFilter : Component { public Mesh sharedMesh; }
    public class Mesh : Object { public int subMeshCount, vertexCount; public Vector3[] vertices; public int[] triangles; public uint GetIndexCount(int s) => 0; }
    public class Material : Object { public Material(Shader s) { } public Color color; }
    public class Shader : Object { public static Shader Find(string n) => null; }
    public struct Color { public float r, g, b, a; public Color(float r, float g, float b) { this.r = r; this.g = g; this.b = b; a = 1; } }
    public struct Rect { public Rect(float x, float y, float w, float h) { } }
    public enum PrimitiveType { Sphere, Cube, Cylinder }
    public enum LightType { Directional, Point }
    public enum CameraClearFlags { SolidColor }
    public enum TextureFormat { RGB24 }
    public class Light : Component { public LightType type; public float intensity; }
    public class Camera : Component { public CameraClearFlags clearFlags; public Color backgroundColor; public bool orthographic; public float orthographicSize, nearClipPlane, farClipPlane; public RenderTexture targetTexture; public void Render() { } }
    public class RenderTexture : Object { public static RenderTexture active; public RenderTexture(int w, int h, int d) { } }
    public class Texture2D : Object { public Texture2D(int w, int h, TextureFormat f, bool m) { } public void ReadPixels(Rect r, int x, int y) { } public byte[] EncodeToPNG() => null; }
    public static class RenderSettings { public static Rendering.AmbientMode ambientMode; public static Color ambientLight; }
    namespace Rendering { public enum AmbientMode { Flat } }
    public class Collider : Component { public bool enabled; }
    public class MeshCollider : Collider { public Mesh sharedMesh; }
    public class Collider2D : Behaviour { }
    public class Rigidbody2D : Component { }
    public class Joint2D : Behaviour { }
    public class Effector2D : Behaviour { }
    public class AudioSource : Behaviour { public AudioClip clip; }
    public class AudioClip : Object { }
    public class AnimationClip : Object { public float length; public float frameRate; public void SampleAnimation(GameObject go, float t) { } }
    public class AssetBundle : Object
    {
        public static AssetBundle LoadFromFile(string path) => null;
        public string[] GetAllAssetNames() => null;
        public Object[] LoadAllAssets() => null;
        public void Unload(bool unloadAllLoadedObjects) { }
    }
    public struct RaycastHit { public Collider collider; public float distance; public Vector3 point, normal; }
    public enum QueryTriggerInteraction { UseGlobal, Ignore, Collide }
    public struct PhysicsScene { public int Raycast(Vector3 o, Vector3 d, RaycastHit[] hits, float dist, int mask, QueryTriggerInteraction q) => 0; }
    public static class PhysicsSceneExtensions { public static PhysicsScene GetPhysicsScene(this SceneManagement.Scene s) => default(PhysicsScene); }
    public static class Physics { public static void SyncTransforms() { } }
    public static class Mathf { public static int RoundToInt(float f) => 0; public static float Abs(float f) => f; public static float Max(float a, float b) => a; public static float Min(float a, float b) => a; public static float Round(float f) => f; public static float Sign(float f) => f; public static float Ceil(float f) => f; public static int Max(int a, int b) => a; public static int Min(int a, int b) => a; public static float Cos(float f) => f; public static float Sin(float f) => f; public const float Deg2Rad = 0.0174f; }
    public static class Debug { public static void Log(object o) { } public static void LogException(Exception e) { } }
    public static class Application { public static string dataPath, unityVersion; }
    public static class JsonUtility { public static T FromJson<T>(string s) => default(T); public static string ToJson(object o, bool pretty) => ""; }
    namespace SceneManagement { public struct Scene { } }
}

namespace UnityEditor
{
    using UnityEngine;
    public struct EditorCurveBinding { public string path, propertyName; public Type type; }
    public class AnimationCurve { public AnimationCurve(params Keyframe[] k) { } public Keyframe[] keys; }
    public struct Keyframe { public Keyframe(float t, float v, float i, float o) { time = t; value = v; inTangent = i; outTangent = o; } public float time, value, inTangent, outTangent; }
    public class ObjectReferenceKeyframe { }
    public static class AnimationUtility
    {
        public static EditorCurveBinding[] GetCurveBindings(AnimationClip c) => null;
        public static EditorCurveBinding[] GetObjectReferenceCurveBindings(AnimationClip c) => null;
        public static void SetEditorCurve(AnimationClip c, EditorCurveBinding b, AnimationCurve curve) { }
        public static AnimationCurve GetEditorCurve(AnimationClip c, EditorCurveBinding b) => null;
        public static void SetObjectReferenceCurve(AnimationClip c, EditorCurveBinding b, ObjectReferenceKeyframe[] k) { }
        public static string CalculateTransformPath(Transform t, Transform root) => "";
    }
    public static class AssetDatabase
    {
        public static T LoadAssetAtPath<T>(string p) where T : Object => null;
        public static void SaveAssets() { } public static void Refresh() { }
        public static void CreateAsset(Object o, string p) { }
        public static bool IsValidFolder(string p) => false;
        public static string CreateFolder(string parent, string name) => "";
        public static string[] FindAssets(string filter, string[] folders) => null;
        public static string GUIDToAssetPath(string g) => "";
        public static string[] GetDependencies(string[] paths, bool recursive) => null;
        public static Type GetMainAssetTypeAtPath(string p) => null;
    }
    public enum PrefabUnpackMode { OutermostRoot, Completely }
    public enum InteractionMode { AutomatedAction, UserAction }
    public static class PrefabUtility
    {
        public static Object InstantiatePrefab(Object o) => null;
        public static void UnpackPrefabInstance(GameObject go, PrefabUnpackMode m, InteractionMode i) { }
        public static GameObject LoadPrefabContents(string p) => null;
        public static void UnloadPrefabContents(GameObject go) { }
        public static GameObject SaveAsPrefabAsset(GameObject go, string p) => null;
        public static GameObject SaveAsPrefabAsset(GameObject go, string p, out bool success) { success = false; return null; }
    }
    public static class GameObjectUtility { public static int RemoveMonoBehavioursWithMissingScript(GameObject go) => 0; }
    public static class EditorApplication { public static void Exit(int code) { } }
    public static class EditorUtility { public static void SetDirty(Object o) { } }
    public enum SerializedPropertyType { Generic, Integer, Boolean, Float, String, Color, ObjectReference }
    public class SerializedProperty
    {
        public bool Next(bool enterChildren) => false;
        public SerializedPropertyType propertyType; public string stringValue; public float floatValue; public int arraySize;
        public Object objectReferenceValue; public SerializedProperty GetArrayElementAtIndex(int i) => null;
    }
    public class SerializedObject { public SerializedObject(Object o) { } public SerializedProperty FindProperty(string n) => null; public SerializedProperty GetIterator() => null; }
    namespace SceneManagement
    {
        public enum NewSceneSetup { EmptyScene, DefaultGameObjects }
        public enum NewSceneMode { Single, Additive }
        public static class EditorSceneManager { public static UnityEngine.SceneManagement.Scene NewScene(NewSceneSetup s, NewSceneMode m) => default(UnityEngine.SceneManagement.Scene); }
    }
}

// the builder core's loader entry point, which Rr2dvBuild hands over to (tooling/builder/tools/unity/LlwVehicleRecord.cs)
public static class CclLocoBuild { public static void RunRr2dvRecord() { } }
