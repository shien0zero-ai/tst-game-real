using UnrealBuildTool;
public class AshgateForestLightingLabEditorTarget : TargetRules { public AshgateForestLightingLabEditorTarget(TargetInfo Target) : base(Target) { Type=TargetType.Editor; DefaultBuildSettings=BuildSettingsVersion.Latest; IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8; ExtraModuleNames.Add("ForestTrail"); } }
