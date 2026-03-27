using System.Collections.Generic;
using System.Linq;
using UnityEditor;
using UnityEngine;

public static class AssetUpgrader
{
    public static void UpgradeProject()
    {
        AssetTools.ForceReserializeAssets();
        FixAnimationClips();
    }

    private static void FixAnimationClips()
    {
        var animationGuids = AssetDatabase.FindAssets("t:AnimationClip");
        foreach (var guid in animationGuids)
        {
            var path = AssetDatabase.GUIDToAssetPath(guid);
            var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
            if (clip == null)
            {
                continue;
            }

            var bindings = AnimationUtility.GetCurveBindings(clip);
            var rotationGroups = bindings
                .Where(b => b.propertyName.StartsWith("localEulerAnglesRaw."))
                .GroupBy(b => b.path)
                .ToList();

            if (!rotationGroups.Any())
            {
                continue;
            }

            foreach (var group in rotationGroups)
            {
                var transformPath = group.Key;

                var curveX = AnimationUtility.GetEditorCurve(clip, group.FirstOrDefault(b => b.propertyName.EndsWith(".x")));
                var curveY = AnimationUtility.GetEditorCurve(clip, group.FirstOrDefault(b => b.propertyName.EndsWith(".y")));
                var curveZ = AnimationUtility.GetEditorCurve(clip, group.FirstOrDefault(b => b.propertyName.EndsWith(".z")));

                var timeStamps = new SortedSet<float>();
                if (curveX != null)
                {
                    foreach (var k in curveX.keys)
                    {
                        timeStamps.Add(k.time);
                    }
                }

                if (curveY != null)
                {
                    foreach (var k in curveY.keys)
                    {
                        timeStamps.Add(k.time);
                    }
                }

                if (curveZ != null)
                {
                    foreach (var k in curveZ.keys)
                    {
                        timeStamps.Add(k.time);
                    }
                }

                var qX = new AnimationCurve();
                var qY = new AnimationCurve();
                var qZ = new AnimationCurve();
                var qW = new AnimationCurve();

                foreach (var t in timeStamps)
                {
                    var x = curveX?.Evaluate(t) ?? 0;
                    var y = curveY?.Evaluate(t) ?? 0;
                    var z = curveZ?.Evaluate(t) ?? 0;

                    var q = Quaternion.Euler(x, y, z);

                    qX.AddKey(t, q.x);
                    qY.AddKey(t, q.y);
                    qZ.AddKey(t, q.z);
                    qW.AddKey(t, q.w);
                }

                SetRotationCurve(clip, transformPath, "localRotation.x", qX);
                SetRotationCurve(clip, transformPath, "localRotation.y", qY);
                SetRotationCurve(clip, transformPath, "localRotation.z", qZ);
                SetRotationCurve(clip, transformPath, "localRotation.w", qW);

                AnimationUtility.SetEditorCurve(clip, group.FirstOrDefault(b => b.propertyName.EndsWith(".x")), null);
                AnimationUtility.SetEditorCurve(clip, group.FirstOrDefault(b => b.propertyName.EndsWith(".y")), null);
                AnimationUtility.SetEditorCurve(clip, group.FirstOrDefault(b => b.propertyName.EndsWith(".z")), null);
            }

            clip.EnsureQuaternionContinuity();

            EditorUtility.SetDirty(clip);
            Debug.Log($"Converted rotation to Quaternion for: {path}");
        }

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();
    }

    private static void SetRotationCurve(AnimationClip clip, string path, string property, AnimationCurve curve)
    {
        var binding = EditorCurveBinding.FloatCurve(path, typeof(Transform), property);
        AnimationUtility.SetEditorCurve(clip, binding, curve);
    }
}