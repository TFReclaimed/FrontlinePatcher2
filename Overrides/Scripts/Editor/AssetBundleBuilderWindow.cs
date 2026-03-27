using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public class AssetBundleBuilderWindow : EditorWindow
{
    private bool _buildWindows;

    private bool _buildLinux;

    private bool _buildMacOS;

    private bool _buildAndroid;

    private bool _buildIOS;

    private void OnEnable()
    {
        _buildWindows = EditorUserBuildSettings.activeBuildTarget == BuildTarget.StandaloneWindows64;
        _buildLinux = EditorUserBuildSettings.activeBuildTarget == BuildTarget.StandaloneLinux64;
        _buildMacOS = EditorUserBuildSettings.activeBuildTarget == BuildTarget.StandaloneOSX;
        _buildAndroid = EditorUserBuildSettings.activeBuildTarget == BuildTarget.Android;
        _buildIOS = EditorUserBuildSettings.activeBuildTarget == BuildTarget.iOS;
    }

    private void OnGUI()
    {
        GUILayout.Label("Select Build Targets", EditorStyles.boldLabel);

        _buildWindows = EditorGUILayout.Toggle("Windows", _buildWindows);
        _buildLinux = EditorGUILayout.Toggle("Linux", _buildLinux);
        _buildMacOS = EditorGUILayout.Toggle("macOS", _buildMacOS);
        _buildAndroid = EditorGUILayout.Toggle("Android", _buildAndroid);
        _buildIOS = EditorGUILayout.Toggle("iOS", _buildIOS);

        GUILayout.Space(20);

        if (GUILayout.Button("Build"))
        {
            BuildSelected();
        }
    }

    private void BuildSelected()
    {
        var targets = new List<BuildTarget>();

        if (_buildWindows)
        {
            targets.Add(BuildTarget.StandaloneWindows64);
        }

        if (_buildLinux)
        {
            targets.Add(BuildTarget.StandaloneLinux64);
        }

        if (_buildMacOS)
        {
            targets.Add(BuildTarget.StandaloneOSX);
        }

        if (_buildAndroid)
        {
            targets.Add(BuildTarget.Android);
        }

        if (_buildIOS)
        {
            targets.Add(BuildTarget.iOS);
        }

        if (targets.Count == 0)
        {
            EditorUtility.DisplayDialog("Error", "Please select at least one build target.", "OK");
            return;
        }

        var basePath = EditorUtility.SaveFolderPanel("Save AssetBundles", "", "");
        if (string.IsNullOrEmpty(basePath))
        {
            return;
        }

        foreach (var target in targets)
        {
            var targetPath = basePath;
            if (targets.Count > 1)
            {
                targetPath = Path.Combine(basePath, target.ToString());
            }

            if (!Directory.Exists(targetPath))
            {
                Directory.CreateDirectory(targetPath);
            }

            BuildPipeline.BuildAssetBundles(targetPath, BuildAssetBundleOptions.None, target);
        }

        Close();
        GUIUtility.ExitGUI();
    }
}