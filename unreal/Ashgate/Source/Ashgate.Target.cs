using UnrealBuildTool;
public class AshgateTarget : TargetRules {
    public AshgateTarget(TargetInfo Target) : base(Target) {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
        ExtraModuleNames.Add("Ashgate");
    }
}
