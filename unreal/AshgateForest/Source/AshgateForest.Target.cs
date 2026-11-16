using UnrealBuildTool;
public class AshgateForestTarget : TargetRules { public AshgateForestTarget(TargetInfo Target) : base(Target) { Type=TargetType.Game; DefaultBuildSettings=BuildSettingsVersion.Latest; IncludeOrderVersion=EngineIncludeOrderVersion.Unreal5_8; ExtraModuleNames.Add("ForestTrail"); } }
