using System;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static partial class CclLocoBuild
{
    // A source clip's easing describes playback time, not a physical handle's displacement.
    // Reparameterize only monotonic single-axis motion. Compound motion keeps its click route.
    static AnimationClip RrDirectOpeningClip(RrOpening opening)
    {
        var source = Clip(opening.clip);
        var hinge = RefBody.Find(opening.hinge);
        var target = RefBody.Find(opening.target);
        source.SampleAnimation(RefBody.gameObject, 0);
        var p0 = hinge.position; var q0 = hinge.rotation;
        var relative = hinge.InverseTransformPoint(target.position);
        var rotation = Quaternion.Inverse(q0) * target.rotation;
        source.SampleAnimation(RefBody.gameObject, source.length);
        var p1 = hinge.position; var q1 = hinge.rotation;
        float angle = Quaternion.Angle(q0,q1), distance = Vector3.Distance(p0,p1);
        bool slide = angle < .05f && distance > .01f;
        bool rotate = distance < .001f && angle > .5f && angle < 179.9f;
        float Progress() => slide ? Vector3.Dot(hinge.position-p0, p1-p0)/(distance*distance) : Quaternion.Angle(q0,hinge.rotation)/angle;
        bool simple = slide || rotate; float previous = -1;
        try
        {
            for (int i=0; i<=256 && simple; i++)
            {
                source.SampleAnimation(RefBody.gameObject,source.length*i/256f);
                float p=Progress();
                simple = p >= previous-.00001f && p >= -.00001f && p <= 1.00001f &&
                    Vector3.Distance(hinge.position,Vector3.Lerp(p0,p1,p)) < .0005f &&
                    Quaternion.Angle(hinge.rotation,Quaternion.Slerp(q0,q1,p)) < .05f &&
                    Vector3.Distance(relative,hinge.InverseTransformPoint(target.position)) < .0005f &&
                    Quaternion.Angle(rotation,Quaternion.Inverse(hinge.rotation)*target.rotation) < .05f;
                previous=p;
            }
            if (!simple) return source;
            var bindings=AnimationUtility.GetCurveBindings(source);
            var curves=bindings.Select(b=>AnimationUtility.GetEditorCurve(source,b)).ToArray();
            var keys=bindings.Select(b=>new Keyframe[129]).ToArray();
            for (int i=0;i<=128;i++)
            {
                float progress=i/128f, lo=0, hi=source.length;
                for(int j=0;j<20;j++)
                {
                    float mid=(lo+hi)/2; source.SampleAnimation(RefBody.gameObject,mid);
                    if(Progress()<progress)lo=mid;else hi=mid;
                }
                float time=i==0?0:i==128?source.length:(lo+hi)/2;
                for(int b=0;b<bindings.Length;b++)keys[b][i]=new Keyframe(progress*source.length,curves[b].Evaluate(time));
            }
            var motion=new AnimationClip { name=opening.name+"Displacement", frameRate=source.frameRate };
            for(int b=0;b<bindings.Length;b++)
            {
                var curve=new AnimationCurve(keys[b]);
                for(int k=0;k<curve.length;k++)
                {
                    AnimationUtility.SetKeyLeftTangentMode(curve,k,AnimationUtility.TangentMode.Linear);
                    AnimationUtility.SetKeyRightTangentMode(curve,k,AnimationUtility.TangentMode.Linear);
                }
                AnimationUtility.SetEditorCurve(motion,bindings[b],curve);
            }
            Folder($"{Work}/Animators");
            AssetDatabase.CreateAsset(motion,$"{Work}/Animators/{opening.name}Displacement.anim");
            Line($"rr2dv opening {opening.clip}: monotonic {(slide?"slide":"hinge")} driven by displacement; source poses retained, playback easing removed");
            return motion;
        }
        finally { source.SampleAnimation(RefBody.gameObject,0); }
    }
}
