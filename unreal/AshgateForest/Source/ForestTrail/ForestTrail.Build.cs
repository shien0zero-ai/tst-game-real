using UnrealBuildTool;
public class ForestTrail : ModuleRules { public ForestTrail(ReadOnlyTargetRules Target) : base(Target) { PCHUsage=PCHUsageMode.UseExplicitOrSharedPCHs; PublicDependencyModuleNames.AddRange(new[]{"Core","CoreUObject","Engine","InputCore"}); if(Target.bBuildEditor) PrivateDependencyModuleNames.AddRange(new[]{"UnrealEd","LevelEditor"}); } }
