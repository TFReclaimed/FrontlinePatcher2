using System;
using UnityEditor;
using UnityEngine;

public static class AssetTools
{
    [MenuItem("Assets/TF Reclaimed/Build AssetBundles")]
    private static void BuildAssetBundles()
    {
        EditorWindow.GetWindow<AssetBundleBuilderWindow>(true, "Build AssetBundles", true);
    }

    [MenuItem("Assets/TF Reclaimed/Force Reserialize Assets")]
    public static void ForceReserializeAssets()
    {
        AssetDatabase.ForceReserializeAssets();
        AssetDatabase.SaveAssets();
    }

    public static void BuildAssetBundlesCi()
    {
        var args = Environment.GetCommandLineArgs();
        string assetBundlePath = null;
        for (var i = 0; i < args.Length; i++)
        {
            if (args[i] == "-assetbundlePath")
            {
                assetBundlePath = args[i + 1];
                break;
            }
        }

        if (string.IsNullOrEmpty(assetBundlePath))
        {
            Debug.LogError("No asset bundle path provided!");
            return;
        }

        BuildPipeline.BuildAssetBundles(assetBundlePath, BuildAssetBundleOptions.None,
            EditorUserBuildSettings.activeBuildTarget);

        Debug.Log("Asset bundles successfully built at: " + assetBundlePath);
    }
}
