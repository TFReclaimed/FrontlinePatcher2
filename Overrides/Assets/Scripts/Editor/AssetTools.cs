using UnityEditor;

public static class AssetTools
{
    [MenuItem("Assets/TF Reclaimed/Build AssetBundles")]
    private static void BuildAllAssetBundles()
    {
        EditorWindow.GetWindow<AssetBundleBuilderWindow>(true, "Build AssetBundles", true);
    }

    [MenuItem("Assets/TF Reclaimed/Force Reserialize Assets")]
    public static void ForceReserializeAssets()
    {
        AssetDatabase.ForceReserializeAssets();
        AssetDatabase.SaveAssets();
    }
}
