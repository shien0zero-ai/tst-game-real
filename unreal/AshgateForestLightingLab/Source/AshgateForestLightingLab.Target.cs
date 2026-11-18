using UnrealBuildTool;
public class AshgateForestLightingLabTarget : TargetRules { public AshgateForestLightingLabTarget(TargetInfo Target) : base(Target) { Type=TargetType.Game; DefaultBuildSettings=BuildSettingsVersion.Latest; IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8; ExtraModuleNames.Add("ForestTrail"); } }
