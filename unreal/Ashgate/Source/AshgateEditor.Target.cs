using UnrealBuildTool;
public class AshgateEditorTarget : TargetRules {
    public AshgateEditorTarget(TargetInfo Target) : base(Target) {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("Ashgate");
    }
}
