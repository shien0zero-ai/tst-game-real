using UnrealBuildTool;
public class AshgateForestEditorTarget : TargetRules { public AshgateForestEditorTarget(TargetInfo Target) : base(Target) { Type=TargetType.Editor; DefaultBuildSettings=BuildSettingsVersion.Latest; IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8; ExtraModuleNames.Add("ForestTrail"); } }
