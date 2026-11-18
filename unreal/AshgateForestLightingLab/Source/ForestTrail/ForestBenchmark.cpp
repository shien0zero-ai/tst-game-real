#include "Forest.h"
#include "Camera/CameraComponent.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "GameFramework/Controller.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/PlatformTime.h"
#include "HAL/FileManager.h"
#include "RHI.h"
#include "HAL/FileManager.h"

// Real wall-clock intervals, no fixed timestep, frame-time clamp, screenshots or concurrent cooks.
void AForestMode::BenchmarkTick(){
 auto* P=Player();if(!P||Paused)return;const double Now=FPlatformTime::Seconds();
 if(BenchmarkStart==0){BenchmarkStart=BenchmarkLast=Now;BenchmarkSamples=TEXT("seconds,segment,frame_ms,gpu_ms,game_ms,render_ms\n");}
 const double T=Now-BenchmarkStart,Delta=Now-BenchmarkLast;BenchmarkLast=Now;
 const int32 Segment=FMath::Min(2,int32(T/35));const double Local=T-Segment*35;
 if(Segment!=BenchmarkSegment){BenchmarkSegment=Segment;const float X=Segment==0?-85:Segment==1?-75:-72,Y=TrailY(X)+(Segment==1?3:0);P->SetActorLocation(FVector(X*100,Y*100,Height(X,Y)*100+180));P->Controller->SetControlRotation(FRotator(-3,Segment==1?25:12,0));}
 // Each segment: 10 seconds settle, then a 25-second view/slow walking route.
 if(Local>=10&&T<105){
  if(Segment!=1)P->AddMovementInput(FVector(1,0,0),.2f);
  P->Controller->SetControlRotation(FRotator(-3+(Segment==1?3*FMath::Sin(Local*.14):0),12+(Segment==1?35*FMath::Sin(Local*.12):5*FMath::Sin(Local*.15)),0));
  BenchmarkSamples+=FString::Printf(TEXT("%.6f,%d,%.6f,%.6f,%.6f,%.6f\n"),T,Segment,Delta*1000,FPlatformTime::ToMilliseconds(RHIGetGPUFrameCycles()),FPlatformTime::ToMilliseconds(GGameThreadTime),FPlatformTime::ToMilliseconds(GRenderThreadTime));
 }
 if(T>=105){const FString Path=FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Performance/ForestBenchmark.csv"));IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path),true);FFileHelper::SaveStringToFile(BenchmarkSamples,*Path);UE_LOG(LogTemp,Display,TEXT("FOREST BENCHMARK COMPLETE resolution=commandline screenpercentage=100 scalability=4 path=%s"),*Path);FPlatformMisc::RequestExit(false);}
}
