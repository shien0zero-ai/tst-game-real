#include "Forest.h"
#include "Camera/CameraComponent.h"
#include "Components/BoxComponent.h"
#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "AudioMixerBlueprintLibrary.h"
#include "Misc/Paths.h"
#include "HAL/PlatformTime.h"
#include "Sound/SoundAttenuation.h"
#include "HAL/IConsoleManager.h"

// Isolated real-audio distance/occlusion regression, available only by explicit launch flag.
void AForestMode::AcousticQATick(){
 auto* P=Player();if(!P)return;const double Now=FPlatformTime::Seconds();
 if(AcousticStart==0){AcousticStart=Now;P->ForestAcousticProbe=true;if(auto* C=IConsoleManager::Get().FindConsoleVariable(TEXT("au.NeverDisableSubmixes")))C->Set(1,ECVF_SetByCode);P->WindAudio->SetVolumeMultiplier(0);P->BirdsAudio->SetVolumeMultiplier(0);P->GetCharacterMovement()->SetMovementMode(MOVE_Flying);P->SetActorLocation(FVector(0,0,15000));}
 const double T=Now-AcousticStart;
 if(AcousticStage==0&&T>=5){UAudioMixerBlueprintLibrary::StartRecordingOutput(this,30);AcousticRecordStart=Now;AcousticStage=1;}
 if(AcousticStage<1)return;const double R=Now-AcousticRecordStart;
 if(AcousticStage>=1&&AcousticStage<=5){const int32 Test=AcousticStage-1;const float Meters=Test==0?0:Test==1?10:Test==3?100:50;const double Due=1+Test*5+Meters/343.;
  if(R>=Due){const FVector Listener=P->Camera->GetComponentLocation();FVector Source=Listener+FVector(Meters*100,0,0);
   if(Test==4){auto* Wall=GetWorld()->SpawnActor<AActor>();auto* B=NewObject<UBoxComponent>(Wall);Wall->SetRootComponent(B);B->SetBoxExtent(FVector(30,300,300));B->SetCollisionEnabled(ECollisionEnabled::QueryOnly);B->SetCollisionResponseToAllChannels(ECR_Ignore);B->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);B->RegisterComponent();B->SetWorldLocation(Listener+FVector(2500,0,0));}
   FHitResult Hit;FCollisionQueryParams Q;Q.AddIgnoredActor(P);const bool Blocked=GetWorld()->LineTraceSingleByChannel(Hit,Source,Listener,ECC_Visibility,Q);
   Check(Blocked==(Test==4),TEXT("isolated acoustic source visibility matches scenario"));
   P->EmitGunshot(Test==0?Listener+FVector(45,0,0):Source,Test==0,0);
   UE_LOG(LogTemp,Display,TEXT("ACOUSTIC QA event=%d recording_s=%.4f distance_m=%.1f blocked=%d"),Test,R,Meters,Blocked);++AcousticStage;
  }
 }
 if(AcousticStage==6&&R>=26){UAudioMixerBlueprintLibrary::StopRecordingOutput(this,EAudioRecordingExportType::WavFile,TEXT("DistanceOcclusion"),FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir()/TEXT("AudioQA")));AcousticStage=7;}
 if(AcousticStage==7&&R>=30){UE_LOG(LogTemp,Display,TEXT("ACOUSTIC QA COMPLETE failures=%d"),Failures);FPlatformMisc::RequestExitWithStatus(false,Failures?1:0);}
}
