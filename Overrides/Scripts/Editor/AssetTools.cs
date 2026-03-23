using UnityEditor;

public static class AssetTools
{
    [MenuItem("Assets/TF Reclaimed/Build AssetBundles")]
    private static void BuildAllAssetBundles()
    {
        var path = EditorUtility.SaveFolderPanel("Save AssetBundles", "", "");
        if (string.IsNullOrEmpty(path))
        {
            return;
        }

        // TODO: Ask for build target
        BuildPipeline.BuildAssetBundles(path, BuildAssetBundleOptions.None, BuildTarget.StandaloneLinux64);
    }

    [MenuItem("Assets/TF Reclaimed/Force Reserialize Assets")]
    public static void ForceReserializeAssets()
    {
        AssetDatabase.ForceReserializeAssets();
        AssetDatabase.SaveAssets();
    }
}
