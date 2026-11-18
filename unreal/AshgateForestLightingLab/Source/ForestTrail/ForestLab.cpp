#include "Forest.h"
#include "Engine/World.h"
#include "Engine/Level.h"
#include "Engine/MapBuildDataRegistry.h"
#include "EngineUtils.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/ReflectionCapture.h"
#include "GameFramework/WorldSettings.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Containers/Ticker.h"
#include "Misc/Crc.h"
#include "PrecomputedVolumetricLightmap.h"
#if WITH_EDITOR
#include "Editor.h"
#include "FileHelpers.h"
#include "UObject/Package.h"
#include "UObject/UObjectIterator.h"
#include "Misc/PackageName.h"
#include "HAL/FileManager.h"
#include "LightingBuildOptions.h"
#include "Builders/CubeBuilder.h"
#include "Lightmass/LightmassImportanceVolume.h"
#include "Engine/SphereReflectionCapture.h"
#include "Components/SphereReflectionCaptureComponent.h"
#endif

static void LabCVar(const TCHAR* Name,int32 V){if(auto* C=IConsoleManager::Get().FindConsoleVariable(Name))C->Set(V,ECVF_SetByConsole);}
void InitializeForestLab(AForestMode* M){
 auto* W=M->GetWorld();const bool Full=FParse::Param(FCommandLine::Get(),TEXT("LabFull"));const bool Lumen=Full||FParse::Param(FCommandLine::Get(),TEXT("LabLumen"));
 LabCVar(TEXT("r.DynamicGlobalIlluminationMethod"),Lumen?1:0);LabCVar(TEXT("r.ReflectionMethod"),Lumen?1:2);LabCVar(TEXT("r.Shadow.Virtual.Enable"),1);
 // Populate Nanite geometry before retaining shadow pages. Keep normal caching after warmup.
 LabCVar(TEXT("r.Shadow.Virtual.Cache"),0);const double ShadowWarmStart=FPlatformTime::Seconds();
 FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([ShadowWarmStart](float){if(FPlatformTime::Seconds()-ShadowWarmStart<8)return true;LabCVar(TEXT("r.Shadow.Virtual.Cache"),1);UE_LOG(LogTemp,Display,TEXT("LAB_SHADOW_CACHE_WARMUP COMPLETE cache=1"));return false;}),.1f);
 TArray<AActor*> Remove;
 for(TActorIterator<AActor> It(W);It;++It){auto* A=*It;if((Full&&A->Tags.Contains(TEXT("ForestLabGeometry")))||(Lumen&&A->IsA<AReflectionCapture>()))Remove.Add(A);}
 for(auto* A:Remove)A->Destroy();
 if(Full)M->BuildForest();else{
  M->Trees=M->Plants=0;
  for(TActorIterator<AActor> It(W);It;++It){auto* A=*It;
   if(Lumen&&A->Tags.Contains(TEXT("ForestLabGeometry"))){TArray<USceneComponent*> C;A->GetComponents(C);for(auto* P:C)P->SetMobility(EComponentMobility::Movable);}
   TArray<UHierarchicalInstancedStaticMeshComponent*> C;A->GetComponents(C);for(auto* P:C){const FString N=P->GetStaticMesh()?P->GetStaticMesh()->GetName():TEXT("");if(N.StartsWith(TEXT("pine_"))||N.StartsWith(TEXT("fir_")))M->Trees+=P->GetInstanceCount();else if(N.StartsWith(TEXT("grass_"))||N.StartsWith(TEXT("fern_"))||N.StartsWith(TEXT("sapling_")))M->Plants+=P->GetInstanceCount();}
  }
 }
 // Compare the exact mesh/transform set inside the patch, independently of forest size.
 TArray<FString> Placement;int32 LocalTrees=0,LocalPlants=0;
 for(TActorIterator<AActor> It(W);It;++It){TArray<UHierarchicalInstancedStaticMeshComponent*> C;It->GetComponents(C);for(auto* P:C){if(!P->GetStaticMesh())continue;const FString N=P->GetStaticMesh()->GetName();for(int32 I=0;I<P->GetInstanceCount();++I){FTransform X;P->GetInstanceTransform(I,X,true);const FVector V=X.GetLocation();if(V.X<-10700||V.X>-4300||V.Y<-4100||V.Y>2300)continue;Placement.Add(N+TEXT("|")+X.ToString());if(N.StartsWith(TEXT("pine_"))||N.StartsWith(TEXT("fir_")))++LocalTrees;else if(N.StartsWith(TEXT("grass_"))||N.StartsWith(TEXT("fern_"))||N.StartsWith(TEXT("sapling_")))++LocalPlants;}}}
 Placement.Sort();const FString Signature=FString::Join(Placement,TEXT("\n"));UE_LOG(LogTemp,Display,TEXT("LAB_GEOMETRY patch_instances=%d trees=%d plants=%d placement_crc32=%08X"),Placement.Num(),LocalTrees,LocalPlants,FCrc::StrCrc32(*Signature));
 // Keep the saved indirect light, but evaluate sun direct light and all its shadows dynamically.
 if(!Lumen)for(TActorIterator<ADirectionalLight> It(W);It;++It)It->GetLightComponent()->SetMobility(EComponentMobility::Movable);
 auto* Level=W->PersistentLevel.Get();auto* Data=Level->MapBuildData.Get();int32 Meshes=0,Clusters=0;if(Data)Data->GetLightmapResourceClusterStats(Meshes,Clusters);const auto* Vlm=Data?Data->GetLevelPrecomputedVolumetricLightmapBuildData(Level->LevelBuildDataId):nullptr;const bool Volume=Vlm&&Vlm->BrickDataDimensions.GetMin()>0&&Vlm->BrickData.AmbientVector.DataSize>0;UE_LOG(LogTemp,Display,TEXT("LAB_VOLUME valid=%d brick_texture=%s ambient_bytes=%d"),Volume,Vlm?*Vlm->BrickDataDimensions.ToString():TEXT("none"),Vlm?Vlm->BrickData.AmbientVector.DataSize:0);
 UE_LOG(LogTemp,Display,TEXT("LAB_SETUP mode=%s trees=%d plants=%d surface_mappings=%d clusters=%d volumetric_lightmap=%d / VSM retained for Nanite / Cine 1080p 100%%"),Full?TEXT("FULL_LUMEN"):Lumen?TEXT("PATCH_LUMEN"):TEXT("PATCH_BAKED"),M->Trees,M->Plants,Meshes,Clusters,Volume);
 if(M->QA&&!Lumen)M->Check(Meshes>0&&Volume,TEXT("saved surface and volumetric lighting are present in the baked level"));
}

#if WITH_EDITOR
static bool SaveLabLighting(UWorld* W){
 TArray<UPackage*> Packages;auto* D=W->PersistentLevel->MapBuildData.Get();
 if(!D)return false;D->MarkPackageDirty();W->MarkPackageDirty();
 for(TObjectIterator<UPackage> It;It;++It)if(It->GetName().StartsWith(TEXT("/Game/"))&&It->IsDirty())Packages.AddUnique(*It);
 Packages.AddUnique(D->GetOutermost());Packages.AddUnique(W->GetOutermost());
 if(!UEditorLoadingAndSavingUtils::SavePackages(Packages,false))return false;
 const FString File=FPackageName::LongPackageNameToFilename(D->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());const int64 Size=IFileManager::Get().FileSize(*File);
 UE_LOG(LogTemp,Display,TEXT("LAB_SAVED_LIGHTING file=%s bytes=%lld"),*File,Size);return Size>0;
}
static void EnsureLabImportance(UWorld* W){
 for(TActorIterator<ALightmassImportanceVolume> It(W);It;++It){UE_LOG(LogTemp,Display,TEXT("LAB_IMPORTANCE bounds=%s"),*It->GetComponentsBoundingBox(true).ToString());return;}
 ALightmassImportanceVolume::StaticClass();auto* B=Cast<UCubeBuilder>(GEditor->FindBrushBuilder(UCubeBuilder::StaticClass()));B->X=7600;B->Y=7600;B->Z=5000;B->Build(W,W->GetDefaultBrush());W->GetDefaultBrush()->SetActorLocation(FVector(-7500,-900,1500));GEditor->Exec(W,TEXT("BRUSH ADDVOLUME CLASS=/Script/Engine.LightmassImportanceVolume"));
 for(TActorIterator<ALightmassImportanceVolume> It(W);It;++It)UE_LOG(LogTemp,Display,TEXT("LAB_IMPORTANCE bounds=%s"),*It->GetComponentsBoundingBox(true).ToString());
}
static FAutoConsoleCommand LabCreate(TEXT("ForestLab.Create"),TEXT("Create the saved 64m comparison patch"),FConsoleCommandDelegate::CreateLambda([]{
 UWorld* W=GEditor->GetEditorWorldContext().World();TSet<AActor*> Before;for(TActorIterator<AActor> It(W);It;++It)Before.Add(*It);
 auto* M=W->SpawnActor<AForestMode>();M->BuildForest();
 for(TActorIterator<AActor> It(W);It;++It)if(!Before.Contains(*It)&&*It!=M)(*It)->Tags.AddUnique(TEXT("ForestLabGeometry"));M->Destroy();
 auto* S=W->GetWorldSettings();S->bForceNoPrecomputedLighting=false;S->LightmassSettings.StaticLightingLevelScale=.5f;S->LightmassSettings.NumIndirectLightingBounces=4;S->LightmassSettings.NumSkyLightingBounces=4;S->LightmassSettings.IndirectLightingQuality=2;S->LightmassSettings.VolumeLightingMethod=VLM_VolumetricLightmap;S->LightmassSettings.VolumetricLightmapDetailCellSize=100;S->LightmassSettings.VolumetricLightmapMaximumBrickMemoryMb=128;
 EnsureLabImportance(W);
 auto* Capture=W->SpawnActor<ASphereReflectionCapture>(FVector(-7500,-900,500),FRotator::ZeroRotator);Cast<USphereReflectionCaptureComponent>(Capture->GetCaptureComponent())->InfluenceRadius=5000;Capture->Tags.Add(TEXT("ForestLabCapture"));
 FEditorFileUtils::SaveDirtyPackages(false,true,true,false,false,false);UE_LOG(LogTemp,Display,TEXT("LAB PATCH CREATED"));
}));
static FAutoConsoleCommand LabBake(TEXT("ForestLab.Bake"),TEXT("Build real static lighting and save the result"),FConsoleCommandDelegate::CreateLambda([]{
 UWorld* BakeWorld=GEditor->GetEditorWorldContext().World();EnsureLabImportance(BakeWorld);BakeWorld->PersistentLevel->GetOrCreateMapBuildData();if(!SaveLabLighting(BakeWorld)){UE_LOG(LogTemp,Error,TEXT("LAB SAVE PREFLIGHT FAILED"));FPlatformMisc::RequestExitWithStatus(false,1);return;}
 FLightingBuildOptions Options;Options.QualityLevel=Quality_Production;Options.NumUnusedLocalCores=4;GEditor->BuildLighting(Options);const double Start=FPlatformTime::Seconds();
 FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Start](float){
  const double T=FPlatformTime::Seconds()-Start;if(T>2400){UE_LOG(LogTemp,Error,TEXT("LAB BAKE TIMEOUT"));FPlatformMisc::RequestExitWithStatus(false,1);return false;}
  if(T<3||GEditor->IsLightingBuildCurrentlyRunning())return true;
  UWorld* W=GEditor->GetEditorWorldContext().World();auto* L=W->PersistentLevel.Get();auto* D=L->MapBuildData.Get();int32 Meshes=0,Clusters=0;if(D)D->GetLightmapResourceClusterStats(Meshes,Clusters);const bool Volume=D&&D->GetLevelPrecomputedVolumetricLightmapBuildData(L->LevelBuildDataId)!=nullptr;
  if(!D||!Volume||Meshes==0){UE_LOG(LogTemp,Error,TEXT("LAB BAKE FAILED mappings=%d volume=%d"),Meshes,Volume);FPlatformMisc::RequestExitWithStatus(false,1);return false;}
  GEditor->BuildReflectionCaptures(W);if(!SaveLabLighting(W)){UE_LOG(LogTemp,Error,TEXT("LAB BAKE SAVE FAILED"));FPlatformMisc::RequestExitWithStatus(false,1);return false;}FFileHelper::SaveStringToFile(FString::Printf(TEXT("{\"surface_mappings\":%d,\"clusters\":%d,\"volumetric_lightmap\":true,\"seconds\":%.3f}"),Meshes,Clusters,T),*(FPaths::ProjectSavedDir()/TEXT("lab-bake.json")));UE_LOG(LogTemp,Display,TEXT("LAB BAKE COMPLETE mappings=%d clusters=%d volume=%d seconds=%.1f"),Meshes,Clusters,Volume,T);FPlatformMisc::RequestExit(false);return false;
 }),.5f);
}));
#endif
