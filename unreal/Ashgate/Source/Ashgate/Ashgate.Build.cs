using UnrealBuildTool;
public class Ashgate : ModuleRules {
    public Ashgate(ReadOnlyTargetRules Target) : base(Target) {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new [] { "Core", "CoreUObject", "Engine", "InputCore", "AIModule" });
        if (Target.bBuildEditor) PrivateDependencyModuleNames.AddRange(new [] { "UnrealEd", "LevelEditor" });
    }
}
