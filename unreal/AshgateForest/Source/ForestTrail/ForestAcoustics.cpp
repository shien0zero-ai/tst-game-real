#include "Forest.h"
#include "Camera/CameraComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"
#include "Components/AudioComponent.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"

// Recorded blast/tail layers. No oscillator, pitch drop or feedback-delay reverb.
void AForestPlayer::ConfigureGunAcoustics(){
 GunAttenuation=NewObject<USoundAttenuation>(this);auto& A=GunAttenuation->Attenuation;
 A.bAttenuate=true;A.bSpatialize=true;A.AttenuationShape=EAttenuationShape::Sphere;
 A.AttenuationShapeExtents=FVector(200);A.FalloffDistance=29800;
 A.DistanceAlgorithm=EAttenuationDistanceModel::NaturalSound;A.dBAttenuationAtMax=-50;
 A.bAttenuateWithLPF=true;A.bEnableLogFrequencyScaling=true;A.LPFRadiusMin=3000;A.LPFRadiusMax=18000;A.LPFFrequencyAtMin=18000;A.LPFFrequencyAtMax=2200;
 A.bEnableOcclusion=true;A.OcclusionTraceChannel=ECC_Visibility;A.bUseComplexCollisionForOcclusion=false;A.OcclusionLowPassFilterFrequency=1400;A.OcclusionVolumeAttenuation=.40f;A.OcclusionInterpolationTime=.06f;
 A.bEnableReverbSend=false; // The recorded outdoor decay is the wet layer, not an indoor reverb preset.
 ReflectionAttenuation=NewObject<USoundAttenuation>(this);ReflectionAttenuation->Attenuation=A;
 auto& R=ReflectionAttenuation->Attenuation;R.AttenuationShapeExtents=FVector(1200);R.FalloffDistance=18800;R.dBAttenuationAtMax=-28;R.bEnableOcclusion=false;
 for(const TCHAR* N:{TEXT("woods_tail_0"),TEXT("woods_tail_1"),TEXT("woods_far_0"),TEXT("woods_far_1"),TEXT("woods_action")}){
  auto* S=LoadObject<USoundBase>(nullptr,*(FString(TEXT("/Game/Forest/Acoustics/"))+N+TEXT(".")+N));if(S)Sounds.Add(FName(N),S);else UE_LOG(LogTemp,Error,TEXT("Missing acoustic layer %s"),N);
 }
 for(int32 I=0;I<3;++I){FString N=FString::Printf(TEXT("woods_close_%d"),I);if(auto* S=LoadObject<USoundBase>(nullptr,*(FString(TEXT("/Game/Forest/Acoustics/"))+N+TEXT(".")+N)))Sounds.Add(FName(*FString::Printf(TEXT("service_shot_%d"),I)),S);else UE_LOG(LogTemp,Error,TEXT("Missing acoustic layer %s"),*N);}
}

void AForestPlayer::EmitGunshot(const FVector& At,bool Local,int32 Take){
 const FName Close(*(FString(Legacy1911?TEXT("field_shot_"):TEXT("service_shot_"))+FString::FromInt(Take%3)));
 const FVector Listener=Camera->GetComponentLocation();const float Distance=FVector::Distance(At,Listener);
 if(Local){Sound(Close,.78f);Sound(TEXT("woods_action"),.15f);}
 else {
  // Equal-power near/far blend; propagation delay is elapsed before this function is called.
  const float Blend=FMath::Clamp((Distance-1500.f)/6500.f,0.f,1.f);
  auto Play=[&](FName N,float Gain){if(auto S=Sounds.Find(N))UGameplayStatics::SpawnSoundAttached(S->Get(),Camera,NAME_None,At,FRotator::ZeroRotator,EAttachLocation::KeepWorldPosition,false,Gain,1,0,GunAttenuation);};
  Play(Close,.78f*FMath::Sqrt(1-Blend));Play(FName(*FString::Printf(TEXT("woods_far_%d"),Take%2)),.78f*FMath::Sqrt(Blend));
 }
 // Only a few collision probes per trigger pull, never every frame. Approximate outdoor response,
 // not a claim of material-aware wave propagation or a full acoustic simulation.
 struct Surface{FVector Point;float Distance;};TArray<Surface> Hits;FCollisionQueryParams Q;Q.AddIgnoredActor(this);
 for(int32 I=0;I<8;++I){const float Angle=I*PI/4;FVector Direction(FMath::Cos(Angle),FMath::Sin(Angle),I%2?-.06f:.04f);FHitResult H;
  if(GetWorld()->LineTraceSingleByChannel(H,At,At+Direction*9000,ECC_Visibility,Q)&&H.Distance>500)Hits.Add({H.ImpactPoint,H.Distance});
 }
 Hits.Sort([](const Surface& A,const Surface& B){return A.Distance<B.Distance;});
 // Diffuse open-air decay always exists. Do not add another full-volume attack.
 if(Local)Echoes.Add({FName(*FString::Printf(TEXT("woods_tail_%d"),Take%2)),At,.045f,.28f,false});
 for(int32 I=0;I<FMath::Min(2,Hits.Num());++I){const auto& H=Hits[I];const float Path=H.Distance+FVector::Distance(H.Point,Listener)-(Local?0.f:Distance);
  const float Delay=FMath::Clamp(Path/34300.f,.035f,.55f);const float Gain=.08f/(1+H.Distance/1800.f);
  Echoes.Add({FName(*FString::Printf(TEXT("woods_tail_%d"),(Take+I+1)%2)),H.Point+ (At-H.Point).GetSafeNormal()*30,Delay,Gain,true});
 }
 if(ForestAcousticProbe||FParse::Param(FCommandLine::Get(),TEXT("ForestInput")))UE_LOG(LogTemp,Display,TEXT("ACOUSTIC shot local=%d distance_m=%.1f reflections=%d source_clipping_limit=documented"),Local,Distance/100,FMath::Min(2,Hits.Num()));
}
void AForestPlayer::UpdateGunAcoustics(float D){
 for(int32 I=Echoes.Num()-1;I>=0;--I){auto& E=Echoes[I];E.Delay-=D;if(E.Delay>0)continue;
  if(auto S=Sounds.Find(E.Name)){
   if(E.Spatial)UGameplayStatics::SpawnSoundAtLocation(this,S->Get(),E.Position,FRotator::ZeroRotator,E.Volume,1,0,ReflectionAttenuation);
   else UGameplayStatics::PlaySound2D(this,S->Get(),E.Volume,1,0,nullptr,this,false);
  }Echoes.RemoveAtSwap(I);
 }
}
