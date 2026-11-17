#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/HUD.h"
#include "Kismet/GameplayStatics.h"
#include "Containers/Ticker.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformMisc.h"
#include "HighResScreenshot.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"

// Explicit developer command only: collect a warmed GPU event tree without UI.
static FAutoConsoleCommand ForestProfileGPU(TEXT("Forest.ProfileGPU"),TEXT("Warm up, log GPU event tree and exit"),FConsoleCommandDelegate::CreateLambda([]{
 const double Start=FPlatformTime::Seconds();
 FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Start,Done=false](float) mutable {
  const double Elapsed=FPlatformTime::Seconds()-Start;
  if(!Done&&Elapsed>=20&&GEngine&&GEngine->GameViewport){if(auto* PC=UGameplayStatics::GetPlayerController(GEngine->GameViewport->GetWorld(),0)){
   PC->ConsoleCommand(TEXT("r.ProfileGPU.ShowUI 0"));PC->ConsoleCommand(TEXT("r.ProfileGPU.TableFormatting 0"));PC->ConsoleCommand(TEXT("r.ProfileGPU.UnicodeOutput 0"));PC->ConsoleCommand(TEXT("profilegpu"));Done=true;
  }}
  if(Elapsed>=35){FPlatformMisc::RequestExit(false);return false;}return true;
 }),.1f);
}));

static FAutoConsoleCommand ForestPhoto(TEXT("Forest.Photo"),TEXT("Capture a fixed inspection pose after warmup"),FConsoleCommandDelegate::CreateLambda([]{
 const double Start=FPlatformTime::Seconds();
 FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([Start,Done=false](float) mutable {
  const double Elapsed=FPlatformTime::Seconds()-Start;
  if(!Done&&Elapsed>20){if(GEngine&&GEngine->GameViewport){if(auto* PC=UGameplayStatics::GetPlayerController(GEngine->GameViewport->GetWorld(),0))if(PC->GetHUD())PC->GetHUD()->bShowHUD=false;}FString Name=TEXT("Viewmodel");FParse::Value(FCommandLine::Get(),TEXT("ForestPhotoName="),Name);FScreenshotRequest::RequestScreenshot(FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Photos"),FPaths::MakeValidFileName(Name)+TEXT(".png")),false,false);Done=true;}
  if(Elapsed>24){FPlatformMisc::RequestExit(false);return false;}return true;
 }),.1f);
}));
