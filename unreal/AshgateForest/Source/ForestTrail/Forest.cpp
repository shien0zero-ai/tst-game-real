#include "Forest.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/PostProcessComponent.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/TextureCube.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Sound/SoundBase.h"
#include "Sound/SoundAttenuation.h"
#include "Components/AudioComponent.h"
#include "AudioMixerBlueprintLibrary.h"
#include "Materials/MaterialInterface.h"
#include "HighResScreenshot.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Containers/Ticker.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "Modules/ModuleManager.h"
#if WITH_EDITOR
#include "Editor.h"
#include "PlayInEditorDataTypes.h"
#endif
DEFINE_LOG_CATEGORY_STATIC(LogForest,Log,All);
static AForestMode* Forest(const UObject* O){return Cast<AForestMode>(UGameplayStatics::GetGameMode(O));}
static UStaticMesh* Mesh(const FString& Name){return LoadObject<UStaticMesh>(nullptr,*(TEXT("/Game/Forest/Meshes/")+Name+TEXT(".")+Name));}
AForestPlayer::AForestPlayer(){
 PrimaryActorTick.bCanEverTick=true;GetCapsuleComponent()->InitCapsuleSize(28,88);bUseControllerRotationYaw=true;
 GetCharacterMovement()->MaxWalkSpeed=230;GetCharacterMovement()->MaxWalkSpeedCrouched=120;GetCharacterMovement()->JumpZVelocity=330;GetCharacterMovement()->GetNavAgentPropertiesRef().bCanCrouch=true;
 Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("Eyes"));Camera->SetupAttachment(GetCapsuleComponent());Camera->SetRelativeLocation(FVector(0,0,72));Camera->bUsePawnControlRotation=true;Camera->FieldOfView=82;
 Weapon=CreateDefaultSubobject<USceneComponent>(TEXT("Viewmodel"));Weapon->SetupAttachment(Camera);Weapon->SetRelativeLocation(FVector(38,13,-8));Weapon->SetRelativeRotation(FRotator(0,90,0));
 for(const TCHAR* Part:{TEXT("m1911_frame"),TEXT("m1911_slide"),TEXT("m1911_magazine"),TEXT("grip_right"),TEXT("grip_left")}){
  auto* C=CreateDefaultSubobject<UStaticMeshComponent>(Part);C->SetupAttachment(Weapon);C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->CastShadow=false;
  if(FString(Part)==TEXT("m1911_slide"))Slide=C;if(FString(Part)==TEXT("m1911_magazine"))Magazine=C;if(FString(Part)==TEXT("grip_left"))LeftHand=C;
 }
}
void AForestPlayer::BeginPlay(){Super::BeginPlay();TArray<UStaticMeshComponent*> Parts;GetComponents(Parts);for(auto* C:Parts){if(C->GetAttachParent()!=Weapon.Get())continue;const FString N=C->GetName();C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,*(TEXT("/Game/Art/Meshes/")+N+TEXT(".")+N)));}
 StartForestAudio();}
// New sounds live in the forest project; original Art/Audio assets stay intact.
void AForestPlayer::StartForestAudio(){
 for(const TCHAR* N:{TEXT("forest_wind"),TEXT("forest_birds"),TEXT("step_trail_0"),TEXT("step_trail_1"),TEXT("step_leaves_0"),TEXT("step_leaves_1"),TEXT("pistol_fire_0"),TEXT("pistol_fire_1"),TEXT("pistol_fire_2"),TEXT("mag_out"),TEXT("mag_in"),TEXT("slide_release"),TEXT("dry_fire"),TEXT("gear_rustle"),TEXT("case_soft")}){
  USoundBase* S=LoadObject<USoundBase>(nullptr,*(FString(TEXT("/Game/Forest/Audio/"))+N+TEXT(".")+N));if(S)Sounds.Add(FName(N),S);else UE_LOG(LogForest,Error,TEXT("Missing forest sound %s"),N);
 }
 GroundAttenuation=NewObject<USoundAttenuation>(this);auto& A=GroundAttenuation->Attenuation;A.bSpatialize=true;A.AttenuationShape=EAttenuationShape::Sphere;A.AttenuationShapeExtents=FVector(60);A.FalloffDistance=1400;A.DistanceAlgorithm=EAttenuationDistanceModel::Linear;
 auto Loop=[&](const TCHAR* N,float Gain){auto S=Sounds.Find(FName(N));UAudioComponent* C=S?UGameplayStatics::CreateSound2D(this,S->Get(),1.f,1,0,nullptr,false,false):nullptr;if(C){C->bIsUISound=false;C->FadeIn(2.f,Gain);}return C;};
 WindAudio=Loop(TEXT("forest_wind"),.27f);BirdsAudio=Loop(TEXT("forest_birds"),.24f);LastFootPosition=GetActorLocation();
 UE_LOG(LogForest,Display,TEXT("FOREST AUDIO READY assets=%d wind=%d birds=%d"),Sounds.Num(),WindAudio!=nullptr,BirdsAudio!=nullptr);
}
void AForestPlayer::EndPlay(const EEndPlayReason::Type Reason){for(auto* C:{WindAudio.Get(),BirdsAudio.Get()})if(C){C->Stop();C->DestroyComponent();}Super::EndPlay(Reason);}
void AForestPlayer::SetAudioPaused(bool Value){for(auto* C:{WindAudio.Get(),BirdsAudio.Get()})if(C)C->SetPaused(Value);}
void AForestPlayer::Sound(const FName Name,float Volume,float Pitch){
 if(Forest(this)&&Forest(this)->Paused)return;auto S=Sounds.Find(Name);if(!S)return;
 UGameplayStatics::PlaySound2D(this,S->Get(),Volume,Pitch,0,nullptr,this,false);++SoundEvents.FindOrAdd(Name);
 if(Forest(this)->QA||FParse::Param(FCommandLine::Get(),TEXT("ForestInput")))UE_LOG(LogForest,Display,TEXT("AUDIO event=%s volume=%.2f"),*Name.ToString(),Volume);
}
void AForestPlayer::Footstep(bool Landing){
 const FVector P=GetActorLocation();const bool Trail=FMath::Abs(P.Y/100-AForestMode::TrailY(P.X/100))<1.65f;const FString N=FString(Trail?TEXT("step_trail_"):TEXT("step_leaves_"))+FString::FromInt(FootIndex++%2);auto S=Sounds.Find(FName(*N));if(!S)return;
 const float Gain=Landing?.58f:(bIsCrouched?.17f:(Running?.53f:.37f));const FVector At=P-FVector(0,0,GetCapsuleComponent()->GetScaledCapsuleHalfHeight()-5)+GetActorRightVector()*((FootIndex%2)?12.f:-12.f);
 UGameplayStatics::SpawnSoundAtLocation(this,S->Get(),At,FRotator::ZeroRotator,Gain,FMath::FRandRange(.94f,1.06f),0,GroundAttenuation);++SoundEvents.FindOrAdd(TEXT("footstep"));
 if(Forest(this)->QA||FParse::Param(FCommandLine::Get(),TEXT("ForestInput")))UE_LOG(LogForest,Display,TEXT("AUDIO footstep surface=%s landing=%d crouch=%d run=%d"),Trail?TEXT("trail"):TEXT("leaves"),Landing,bIsCrouched,Running);
 if(Landing||FootIndex%3==0)Sound(TEXT("gear_rustle"),Landing?.26f:(Running?.19f:.10f),FMath::FRandRange(.92f,1.08f));
}
void AForestPlayer::Landed(const FHitResult& Hit){Super::Landed(Hit);if(GetWorld()->GetTimeSeconds()>2&&!Forest(this)->Paused)Footstep(true);FootDistance=0;LastFootPosition=GetActorLocation();}
void AForestPlayer::UpdateFootsteps(float D){
 const FVector P=GetActorLocation();float Distance=FVector::Dist2D(P,LastFootPosition);LastFootPosition=P;
 if(!GetCharacterMovement()->IsMovingOnGround()||Distance>250||GetVelocity().Size2D()<12){FootDistance=0;return;}
 FootDistance+=Distance;const float Stride=bIsCrouched?100.f:(Running?165.f:130.f);if(FootDistance>=Stride){FootDistance=FMath::Fmod(FootDistance,Stride);Footstep();}
}
void AForestPlayer::SetupPlayerInputComponent(UInputComponent* I){Super::SetupPlayerInputComponent(I);
 I->BindAxisKey(EKeys::MouseX,this,&AForestPlayer::Yaw);I->BindAxisKey(EKeys::MouseY,this,&AForestPlayer::Pitch);
 I->BindKey(EKeys::LeftMouseButton,IE_Pressed,this,&AForestPlayer::Fire);I->BindKey(EKeys::RightMouseButton,IE_Pressed,this,&AForestPlayer::Aim);I->BindKey(EKeys::RightMouseButton,IE_Released,this,&AForestPlayer::UnAim);
 I->BindKey(EKeys::R,IE_Pressed,this,&AForestPlayer::Reload);I->BindKey(EKeys::N,IE_Pressed,this,&AForestPlayer::Inspect);I->BindKey(EKeys::SpaceBar,IE_Pressed,this,&ACharacter::Jump);
 I->BindKey(EKeys::LeftShift,IE_Pressed,this,&AForestPlayer::Sprint);I->BindKey(EKeys::LeftShift,IE_Released,this,&AForestPlayer::StopSprint);I->BindKey(EKeys::C,IE_Pressed,this,&AForestPlayer::CrouchToggle);
 I->BindKey(EKeys::F1,IE_Pressed,this,&AForestPlayer::ToggleHelp);I->BindKey(EKeys::F2,IE_Pressed,this,&AForestPlayer::ToggleWeapon);I->BindKey(EKeys::Escape,IE_Pressed,this,&AForestPlayer::Escape).bExecuteWhenPaused=true;
 if(FParse::Param(FCommandLine::Get(),TEXT("ForestInput")))I->BindKey(EKeys::F9,IE_Pressed,this,&AForestPlayer::Capture).bExecuteWhenPaused=true;
}
void AForestPlayer::Forward(float V){if(!Forest(this)->Paused)AddMovementInput(FRotationMatrix(FRotator(0,GetControlRotation().Yaw,0)).GetUnitAxis(EAxis::X),V);}
void AForestPlayer::Right(float V){if(!Forest(this)->Paused)AddMovementInput(FRotationMatrix(FRotator(0,GetControlRotation().Yaw,0)).GetUnitAxis(EAxis::Y),V);}
void AForestPlayer::Yaw(float V){if(!Forest(this)->Paused)AddControllerYawInput(V*Sensitivity);}
void AForestPlayer::Pitch(float V){if(!Forest(this)->Paused)AddControllerPitchInput(-V*Sensitivity);}
void AForestPlayer::Aim(){if(!Forest(this)->Paused&&WeaponShown){if(!Aiming&&ActionSoundCooldown<=0){Sound(TEXT("gear_rustle"),.12f,1.12f);ActionSoundCooldown=.15f;}Aiming=true;InspectTime=0;}}
void AForestPlayer::UnAim(){if(Aiming&&ActionSoundCooldown<=0){Sound(TEXT("gear_rustle"),.10f,.96f);ActionSoundCooldown=.15f;}Aiming=false;}
void AForestPlayer::Reload(){if(!Forest(this)->Paused&&WeaponShown&&Ammo<7&&ReloadTime<=0){ReloadWasEmpty=Ammo==0;ReloadTime=1.35f;InspectTime=0;Aiming=false;Sound(TEXT("mag_out"),.48f);Sound(TEXT("gear_rustle"),.20f);}}
void AForestPlayer::Inspect(){if(!Forest(this)->Paused&&WeaponShown&&ReloadTime<=0){InspectTime=4.2f;Aiming=false;Sound(TEXT("gear_rustle"),.24f,.94f);}}
void AForestPlayer::Fire(){if(Forest(this)->Paused||!WeaponShown)return;InspectTime=0;if(Cooldown>0||ReloadTime>0)return;if(Ammo<=0){Sound(TEXT("dry_fire"),.42f);Cooldown=.22f;return;}--Ammo;Cooldown=.18f;Kick=1;AddControllerPitchInput(-.5f);int32 Take=(LastShot+FMath::RandRange(1,2))%3;LastShot=Take;Sound(FName(*(TEXT("pistol_fire_")+FString::FromInt(Take))),.95f,FMath::FRandRange(.985f,1.015f));CaseDelays.Add(.38f);
 FHitResult Hit;FCollisionQueryParams Q;Q.AddIgnoredActor(this);GetWorld()->LineTraceSingleByChannel(Hit,Camera->GetComponentLocation(),Camera->GetComponentLocation()+Camera->GetForwardVector()*15000,ECC_Visibility,Q);
 UE_LOG(LogForest,Display,TEXT("SHOT ammo=%d impact=%s"),Ammo,Hit.bBlockingHit?*Hit.ImpactPoint.ToString():TEXT("sky"));}
void AForestPlayer::ToggleWeapon(){if(Forest(this)->Paused)return;Sound(TEXT("gear_rustle"),.30f,WeaponShown?.90f:1.05f);WeaponShown=!WeaponShown;Aiming=false;InspectTime=0;}
void AForestPlayer::ToggleHelp(){Help=!Help;}
void AForestPlayer::Sprint(){Running=true;}void AForestPlayer::StopSprint(){Running=false;}
void AForestPlayer::CrouchToggle(){if(bIsCrouched)UnCrouch();else Crouch();}
void AForestPlayer::Escape(){auto* M=Forest(this);if(M->QuitConfirmation){M->QuitConfirmation=false;return;}M->PauseForest(!M->Paused);}
void AForestPlayer::Capture(){UE_LOG(LogForest,Display,TEXT("INPUT position=%s ammo=%d aim=%d reload=%.2f inspect=%.2f visible=%d paused=%d"),*GetActorLocation().ToString(),Ammo,Aiming,ReloadTime,InspectTime,WeaponShown,Forest(this)->Paused);FScreenshotRequest::RequestScreenshot(FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Screenshots/ForestInput.png")),true,true);}
void AForestPlayer::Tick(float D){Super::Tick(D);auto* M=Forest(this);auto* PC=Cast<APlayerController>(Controller);if(!M||!PC||M->Paused)return;
 Forward((PC->IsInputKeyDown(EKeys::W)?1.f:0.f)-(PC->IsInputKeyDown(EKeys::S)?1.f:0.f));Right((PC->IsInputKeyDown(EKeys::D)?1.f:0.f)-(PC->IsInputKeyDown(EKeys::A)?1.f:0.f));
 GetCharacterMovement()->MaxWalkSpeed=Aiming?160:Running?450:230;Cooldown=FMath::Max(0.f,Cooldown-D);Kick=FMath::FInterpTo(Kick,0.f,D,15);
 ActionSoundCooldown=FMath::Max(0.f,ActionSoundCooldown-D);UpdateFootsteps(D);
 for(int32 I=CaseDelays.Num()-1;I>=0;--I){CaseDelays[I]-=D;if(CaseDelays[I]<=0){CaseDelays.RemoveAtSwap(I);auto S=Sounds.Find(TEXT("case_soft"));if(S){UGameplayStatics::SpawnSoundAtLocation(this,S->Get(),GetActorLocation()+GetActorRightVector()*70-FVector(0,0,75),FRotator::ZeroRotator,.12f,FMath::FRandRange(.91f,1.09f),0,GroundAttenuation);++SoundEvents.FindOrAdd(TEXT("case_soft"));}}}
 if(ReloadTime>0){float Before=ReloadTime;ReloadTime=FMath::Max(0.f,ReloadTime-D);if(Before>.47f&&ReloadTime<=.47f)Sound(TEXT("mag_in"),.62f);if(Before>.22f&&ReloadTime<=.22f&&ReloadWasEmpty)Sound(TEXT("slide_release"),.66f);if(ReloadTime<=0)Ammo=7;}InspectTime=FMath::Max(0.f,InspectTime-D);
 FVector P=Aiming?FVector(28,0,-2.9f):FVector(38,13,-8);FRotator R(0,90,0);
 if(InspectTime>0){float T=(4.2f-InspectTime)/4.2f,E=FMath::Sin(PI*T);P+=FVector(-5,-8,7)*E;R+=FRotator(-8*E,50*FMath::Sin(2*PI*T),-12*E);}
 if(ReloadTime>0){float E=FMath::Sin(PI*(1.35f-ReloadTime)/1.35f);R.Roll-=18*E;P.Z-=5*E;}
 P.Z+=FMath::Sin(GetWorld()->GetTimeSeconds()*8)*FMath::Min(1.f,GetVelocity().Size2D()/230)*(Aiming?.03f:.10f);P.X-=Kick*1.5f;
 Weapon->SetRelativeLocation(FMath::VInterpTo(Weapon->GetRelativeLocation(),P,D,12));Weapon->SetRelativeRotation(FMath::RInterpTo(Weapon->GetRelativeRotation(),R,D,13));Weapon->SetVisibility(WeaponShown,true);
 const float ReloadElapsed=1.35f-ReloadTime;const float MagDrop=ReloadTime>0?(ReloadElapsed<.22f?ReloadElapsed/.22f:(ReloadElapsed<.55f?1.f:FMath::Clamp((.88f-ReloadElapsed)/.33f,0.f,1.f))):0.f;
 Slide->SetRelativeLocation(FVector(0,2.8f*((Ammo==0&&(ReloadTime<=0||ReloadTime>.22f))?1:Kick),0));Magazine->SetRelativeLocation(FVector(0,0,-12*MagDrop));LeftHand->SetRelativeLocation(FVector(0,0,-7*MagDrop));Camera->SetFieldOfView(FMath::FInterpTo(Camera->FieldOfView,Aiming?64.f:82.f,D,12));
}
float AForestMode::TrailY(float X){return FMath::Sin(X*.025f)*12+FMath::Sin(X*.065f)*3;}
static float TerrainSample(float X,float Y){float D=Y-AForestMode::TrailY(X);return 5+3*FMath::Sin(X*.018f)+2*FMath::Cos(Y*.027f)+1.2f*FMath::Sin((X+Y)*.035f)-.8f*FMath::Exp(-D*D/12)+.10f*FMath::Sin(X*1.2f)*FMath::Sin(Y*.8f)+.035f*FMath::Sin(X*3+Y*2);}
float AForestMode::Height(float X,float Y){
 // Match the actual one-metre terrain triangles, so small plants do not float.
 float A=FMath::FloorToFloat(X),B=FMath::FloorToFloat(Y),U=X-A,V=Y-B;
 if(U+V<=1)return TerrainSample(A,B)+(TerrainSample(A+1,B)-TerrainSample(A,B))*U+(TerrainSample(A,B+1)-TerrainSample(A,B))*V;
 return TerrainSample(A+1,B+1)+(TerrainSample(A,B+1)-TerrainSample(A+1,B+1))*(1-U)+(TerrainSample(A+1,B)-TerrainSample(A+1,B+1))*(1-V);
}
AForestMode::AForestMode(){DefaultPawnClass=AForestPlayer::StaticClass();HUDClass=AForestHUD::StaticClass();PrimaryActorTick.bCanEverTick=true;}
AForestPlayer* AForestMode::Player()const{return Cast<AForestPlayer>(UGameplayStatics::GetPlayerPawn(this,0));}
void AForestMode::BeginPlay(){Super::BeginPlay();QA=FParse::Param(FCommandLine::Get(),TEXT("ForestQA"));Preview=FParse::Param(FCommandLine::Get(),TEXT("ForestPreview"))||FParse::Param(FCommandLine::Get(),TEXT("GripPreview"));BuildForest();PauseForest(false);ResetTrail();if(auto* PC=UGameplayStatics::GetPlayerController(this,0)){PC->ConsoleCommand(TEXT("scalability 4"));PC->ConsoleCommand(TEXT("r.ScreenPercentage 100"));}UE_LOG(LogForest,Display,TEXT("READY trees=%d plants=%d terrain=256m worldtype=%d / prior games and saves untouched"),Trees,Plants,int32(GetWorld()->WorldType));}
void AForestMode::ResetTrail(){if(auto* P=Player()){float X=-75,Y=TrailY(X);P->SetActorLocation(FVector(X*100,Y*100,Height(X,Y)*100+200));if(P->Controller)P->Controller->SetControlRotation(FRotator(-3,12,0));P->Ammo=7;P->Aiming=false;P->ReloadTime=0;}}
void AForestMode::PauseForest(bool V){Paused=V;if(auto* P=Player())P->SetAudioPaused(V);auto* PC=UGameplayStatics::GetPlayerController(this,0);PC->bShowMouseCursor=V;PC->bEnableClickEvents=V;PC->bEnableMouseOverEvents=V;if(V){FInputModeGameAndUI I;I.SetHideCursorDuringCapture(false);PC->SetInputMode(I);}else{PC->SetInputMode(FInputModeGameOnly());}UGameplayStatics::SetGamePaused(this,V);}
void AForestMode::Action(int32 Row){UE_LOG(LogForest,Display,TEXT("MENU row=%d confirmation=%d"),Row,QuitConfirmation);if(QuitConfirmation){if(Row==1)QuitConfirmation=false;else if(Row==0){UE_LOG(LogForest,Display,TEXT("CONFIRMED USER QUIT"));UGameplayStatics::GetPlayerController(this,0)->ConsoleCommand(TEXT("quit"));}return;}if(Row==0)PauseForest(false);if(Row==1){ResetTrail();PauseForest(false);}if(Row==2)Player()->Sensitivity=FMath::Max(.2f,Player()->Sensitivity-.1f);if(Row==3)Player()->Sensitivity=FMath::Min(3.f,Player()->Sensitivity+.1f);if(Row==4)QuitConfirmation=true;}
void AForestMode::BuildForest(){
 auto* Terrain=GetWorld()->SpawnActor<AStaticMeshActor>();auto* TC=Terrain->GetStaticMeshComponent();TC->SetMobility(EComponentMobility::Movable);TC->SetStaticMesh(Mesh(TEXT("forest_terrain")));TC->SetCollisionProfileName(TEXT("BlockAll"));
 AActor* Root=GetWorld()->SpawnActor<AActor>();auto* Scene=NewObject<USceneComponent>(Root);Root->SetRootComponent(Scene);Scene->RegisterComponent();
 TMap<FString,UHierarchicalInstancedStaticMeshComponent*> Batches;
 auto Instance=[&](const FString& Name,FVector Pos,FRotator Rot,FVector Scale){
  auto*& C=Batches.FindOrAdd(Name);if(!C){C=NewObject<UHierarchicalInstancedStaticMeshComponent>(Root);C->SetMobility(EComponentMobility::Movable);C->SetStaticMesh(Mesh(Name));if(Name.StartsWith(TEXT("moss_rock"))||Name==TEXT("fallen_log")||Name==TEXT("stump"))C->SetCollisionProfileName(TEXT("BlockAll"));else if(Name.StartsWith(TEXT("moss_rock"))||Name==TEXT("stump")||Name==TEXT("fallen_log"))C->SetCollisionProfileName(TEXT("BlockAll"));else C->SetCollisionEnabled(ECollisionEnabled::NoCollision);C->SetupAttachment(Scene);C->RegisterComponent();C->SetCullDistances(0,Name.StartsWith(TEXT("grass"))?6500:Name.StartsWith(TEXT("fern"))?10000:0);}
  C->AddInstance(FTransform(Rot,Pos,Scale),true);
 };
 auto Trunk=[&](FVector Pos,float Radius){AActor* A=GetWorld()->SpawnActor<AActor>(Pos,FRotator::ZeroRotator);auto* C=NewObject<UCapsuleComponent>(A);A->SetRootComponent(C);C->InitCapsuleSize(Radius,220);C->SetCollisionProfileName(TEXT("BlockAll"));C->RegisterComponent();C->SetWorldLocation(Pos+FVector(0,0,190));};
 FRandomStream R(6162026);
 for(int32 I=0;I<35;++I)for(int32 J=0;J<35;++J){float X=-122+I*7.1f+R.FRandRange(-2,2),Y=-122+J*7.1f+R.FRandRange(-2,2);if(FMath::Abs(Y-TrailY(X))<4.8f)continue;float S=R.FRandRange(.9f,1.45f);FVector P(X*100,Y*100,Height(X,Y)*100-5);Instance((I+J)%2==0?TEXT("pine_canopy"):((I+J)%7==0?TEXT("fir_canopy"):TEXT("fir_lush")),P,FRotator(0,R.FRandRange(0,360),0),FVector(S*R.FRandRange(.85f,1.1f),S,S*R.FRandRange(.95f,1.12f)));Trunk(P,24*S);++Trees;}
 for(int32 I=0;I<28000;++I){float X=R.FRandRange(-116,116),Y=I<22000?TrailY(X)+R.FRandRange(-13,13):R.FRandRange(-116,116);float D=FMath::Abs(Y-TrailY(X));if(D<1.4f)continue;float Z=Height(X,Y)*100;FString N;float S;
  if(I%17==0){N=FString::Printf(TEXT("sapling_%c"),TCHAR('a'+I%3));S=R.FRandRange(.8f,2.2f);}else if(I%3==0){N=FString::Printf(TEXT("fern_%d"),I%4);S=R.FRandRange(1.1f,2.0f);}else{const int32 Types[]={0,2,4,7,8};N=FString::Printf(TEXT("grass_%d"),Types[I%5]);S=R.FRandRange(.7f,1.6f);}
  Instance(N,FVector(X*100,Y*100,Z-2),FRotator(0,R.FRandRange(0,360),0),FVector(S));++Plants;
 }
 for(int32 I=0;I<150;++I){float X=R.FRandRange(-105,105),Y=TrailY(X)+R.FRandRange(-18,18);if(FMath::Abs(Y-TrailY(X))<4.5f)continue;float S=R.FRandRange(.65f,1.3f);Instance(FString::Printf(TEXT("moss_rock_%d"),I%6),FVector(X*100,Y*100,Height(X,Y)*100-8),FRotator(0,R.FRandRange(0,360),R.FRandRange(-9,9)),FVector(S));}
 for(int32 I=0;I<18;++I){float X=-90+I*10,Y=TrailY(X)+(I%2?6.f:-8.f);Instance(I%3?TEXT("stump"):TEXT("fallen_log"),FVector(X*100,Y*100,Height(X,Y)*100-8),FRotator(0,I*73,0),FVector(.7f+float(I%3)*.2f));}
 // Deliberate foreground composition beside the first bend, away from the walking corridor.
 for(int32 I=0;I<14;++I){float X=-73+I*.6f,Y=TrailY(X)+(I%2?2.7f:-3.0f);Instance(FString::Printf(TEXT("fern_%d"),I%4),FVector(X*100,Y*100,Height(X,Y)*100),FRotator(0,I*47,0),FVector(1.25f));}
 auto* Sun=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,3000),FRotator(-27,-38,0));auto* Light=Cast<UDirectionalLightComponent>(Sun->GetLightComponent());Light->SetMobility(EComponentMobility::Movable);Light->bAtmosphereSunLight=true;Light->SetIntensity(8500);Light->SetLightColor(FLinearColor(1,.98f,.94f));Light->LightSourceAngle=3.0f;
 auto* Sky=GetWorld()->SpawnActor<ASkyLight>();Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable);Sky->GetLightComponent()->SourceType=SLS_SpecifiedCubemap;Sky->GetLightComponent()->SetCubemap(LoadObject<UTextureCube>(nullptr,TEXT("/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap")));Sky->GetLightComponent()->SetIntensity(500.f);Sky->GetLightComponent()->SetRealTimeCaptureEnabled(false);
 auto* Fog=GetWorld()->SpawnActor<AExponentialHeightFog>(FVector(0,0,800),FRotator::ZeroRotator);Fog->GetComponent()->SetFogDensity(.024f);Fog->GetComponent()->SetFogInscatteringColor(FLinearColor(120,150,180));Fog->GetComponent()->SetFogMaxOpacity(.65f);Fog->GetComponent()->SetFogHeightFalloff(.08f);Fog->GetComponent()->SetStartDistance(300);Fog->GetComponent()->SetVolumetricFog(true);Fog->GetComponent()->SetVolumetricFogScatteringDistribution(.65f);
 auto* Post=NewObject<UPostProcessComponent>(Root);Post->RegisterComponent();Post->bUnbound=true;auto& S=Post->Settings;S.bOverride_AutoExposureMinBrightness=true;S.bOverride_AutoExposureMaxBrightness=true;S.AutoExposureMinBrightness=8.5f;S.AutoExposureMaxBrightness=12.5f;S.bOverride_AutoExposureBias=true;S.AutoExposureBias=-.20f;S.bOverride_ColorGammaShadows=true;S.ColorGammaShadows=FVector4(1,1,1,1.13f);S.bOverride_MotionBlurAmount=true;S.MotionBlurAmount=0;S.bOverride_VignetteIntensity=true;S.VignetteIntensity=0;S.bOverride_BloomIntensity=true;S.BloomIntensity=.08f;
}
void AForestMode::Tick(float D){Super::Tick(D);if(QA||Preview)QATick(D);if(auto* P=Player())if(FMath::Abs(P->GetActorLocation().X)>12100||FMath::Abs(P->GetActorLocation().Y)>12100||P->GetActorLocation().Z<-3000)ResetTrail();}
void AForestMode::Check(bool C,const TCHAR* N){UE_LOG(LogForest,Display,TEXT("QA %s: %s"),C?TEXT("PASS"):TEXT("FAIL"),N);if(!C)++Failures;}
void AForestMode::Shot(const TCHAR* Name){FScreenshotRequest::RequestScreenshot(FPaths::Combine(FPaths::ProjectSavedDir(),FString(TEXT("Screenshots/"))+Name+TEXT(".png")),false,false);}
void AForestMode::QATick(float D){Elapsed+=D;auto* P=Player();if(!P||Elapsed<3)return;if(Step==0&&FParse::Param(FCommandLine::Get(),TEXT("GripPreview"))){ResetTrail();Step=4;Elapsed=0;return;}switch(Step){
 case 0:if(!Preview){if(FParse::Param(FCommandLine::Get(),TEXT("ForestAudioCapture")))UAudioMixerBlueprintLibrary::StartRecordingOutput(this,80);Check(P->Sounds.Num()==15,TEXT("all forest sound assets loaded"));Check(P->WindAudio&&P->BirdsAudio&&P->WindAudio->IsPlaying()&&P->BirdsAudio->IsPlaying(),TEXT("wind and bird loops playing"));auto* FPSHUD=Cast<AForestHUD>(UGameplayStatics::GetPlayerController(this,0)->GetHUD());Check(FPSHUD&&FMath::IsFinite(FPSHUD->CurrentFPS)&&FPSHUD->CurrentFPS>0,TEXT("real-time viewport FPS counter"));Check(Trees>650&&Plants>5000,TEXT("forest population"));Check(P->GetCharacterMovement()->IsMovingOnGround(),TEXT("terrain collision / grounded character"));Check(FMath::Abs((P->GetActorLocation().Z-88)-Height(P->GetActorLocation().X/100,P->GetActorLocation().Y/100)*100)<40,TEXT("terrain elevation matches world"));TArray<UStaticMeshComponent*> Parts;P->GetComponents(Parts);bool Valid=true;int32 WeaponParts=0;for(auto* C:Parts)if(C->GetAttachParent()==P->Weapon.Get()){++WeaponParts;Valid&=C->GetStaticMesh()!=nullptr;}Check(Valid&&WeaponParts==5,TEXT("M1911 and both arms loaded"));Previous=P->GetActorLocation();}++Step;Elapsed=0;break;
 case 1:if(!Preview){P->Forward(1);if(Elapsed<5)break;Check(FVector::Dist(P->GetActorLocation(),Previous)>180,TEXT("walking with terrain collision"));Check(P->SoundEvents.FindRef(TEXT("footstep"))>0,TEXT("grounded movement produces footsteps"));P->Inspect();Check(P->InspectTime>0,TEXT("inspect starts"));P->Aim();Check(P->Aiming&&P->InspectTime==0,TEXT("ADS cancels inspect"));P->UnAim();P->Fire();Check(P->Ammo==6,TEXT("M1911 fire consumes one round"));P->Reload();Check(P->ReloadTime>0,TEXT("reload starts"));}++Step;Elapsed=0;break;
 case 2:if(!Preview){Check(P->Ammo==7&&P->ReloadTime<=0,TEXT("reload completes"));Check(P->SoundEvents.FindRef(TEXT("mag_out"))>0&&P->SoundEvents.FindRef(TEXT("mag_in"))>0,TEXT("reload audio follows magazine timing"));Check(P->SoundEvents.FindRef(TEXT("case_soft"))>0,TEXT("shot casing accent played"));P->Aim();}++Step;Elapsed=0;break;
 case 3:if(!Preview){Check(P->Camera->FieldOfView<70,TEXT("ADS camera"));P->UnAim();P->ToggleWeapon();Check(!P->WeaponShown,TEXT("scenery view / holster"));P->ToggleWeapon();Check(P->WeaponShown,TEXT("M1911 available again"));}ResetTrail();++Step;Elapsed=0;break;
 case 4:if(Elapsed<6)break;Shot(TEXT("Forest-Trail"));++Step;Elapsed=0;break;
 case 5:Sum+=D;Worst=FMath::Max(Worst,double(D));++Frames;if(Elapsed<(FParse::Param(FCommandLine::Get(),TEXT("GripPreview"))?3:12))break;UE_LOG(LogForest,Display,TEXT("PERFORMANCE samples=%d mean=%.2fms fps=%.1f worst=%.2fms / fixed view, warm-up excluded"),Frames,Sum*1000/Frames,Frames/Sum,Worst*1000);P->Inspect();++Step;Elapsed=0;break;
 case 6:Shot(TEXT("Forest-Inspect"));++Step;Elapsed=0;break;
 case 7:P->Aim();++Step;Elapsed=0;break;
 case 8:Shot(TEXT("Forest-ADS"));++Step;Elapsed=0;break;
 case 9:P->UnAim();P->ToggleWeapon();++Step;Elapsed=0;break;
 case 10:Shot(TEXT("Forest-Scenery"));++Step;Elapsed=0;break;
 case 11:{float X=-40,Y=TrailY(X)+3;P->SetActorLocation(FVector(X*100,Y*100,Height(X,Y)*100+180));P->Controller->SetControlRotation(FRotator(-5,25,0));}++Step;Elapsed=0;break;
 case 12:if(Elapsed<5)break;Shot(TEXT("Forest-Grove"));++Step;Elapsed=0;break;
 case 13:if(FParse::Param(FCommandLine::Get(),TEXT("ForestAudioCapture"))){UAudioMixerBlueprintLibrary::StopRecordingOutput(this,EAudioRecordingExportType::WavFile,TEXT("ForestMix"),FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("AudioQA"))));UE_LOG(LogForest,Display,TEXT("AUDIO master submix export requested to Saved/AudioQA/ForestMix.wav"));}++Step;Elapsed=0;break;
 case 14:UE_LOG(LogForest,Display,TEXT("%s COMPLETE failures=%d worldtype=%d"),Preview?TEXT("PREVIEW"):TEXT("QA"),Failures,int32(GetWorld()->WorldType));++Step;
#if WITH_EDITOR
 if(GetWorld()->WorldType==EWorldType::PIE){GEditor->RequestEndPlayMap();FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float){GEditor->Exec(GEditor->GetEditorWorldContext().World(),TEXT("QUIT_EDITOR"));return false;}),2.f);break;}
#endif
 FPlatformMisc::RequestExitWithStatus(false,Failures?1:0);break;}}
void AForestHUD::DrawHUD(){Super::DrawHUD();auto* M=Forest(this);if(!M||!Canvas)return;auto* P=M->Player();float S=Canvas->SizeY/900.f,W=Canvas->SizeX/S;
 auto Text=[&](const FString& T,float X,float Y,float Size=1.f){DrawText(T,FLinearColor(.86f,.89f,.82f),X*S,Y*S,GEngine->GetMediumFont(),Size*S,false);};
 // Wall-clock viewport frames, independent of game pause/time dilation. Refresh 4 times/s.
 const double Now=FPlatformTime::Seconds();
 if(FPSStart==0){FPSStart=Now;FPSFrames=0;}else{++FPSFrames;if(Now-FPSStart>=.25){CurrentFPS=float(FPSFrames/(Now-FPSStart));FPSFrames=0;FPSStart=Now;}}
 DrawRect(FLinearColor(.01f,.02f,.015f,.72f),(W-164)*S,26*S,136*S,38*S);
 Text(CurrentFPS>0?FString::Printf(TEXT("%.0f FPS"),CurrentFPS):TEXT("-- FPS"),W-151,35,.95f);
 if(M->Paused){DrawRect(FLinearColor(.015f,.025f,.02f,.91f),0,0,Canvas->SizeX,Canvas->SizeY);Text(TEXT("ASHGATE / FOREST STUDY"),95,95,1.8f);Text(TEXT("EXPLORE THE TRAIL"),95,155,1.f);TArray<FString> Rows=M->QuitConfirmation?TArray<FString>{TEXT("CONFIRM QUIT TO DESKTOP"),TEXT("CANCEL")} : TArray<FString>{TEXT("RESUME"),TEXT("RETURN TO TRAIL START"),TEXT("SENSITIVITY -"),TEXT("SENSITIVITY +"),TEXT("QUIT TO DESKTOP")};for(int32 I=0;I<Rows.Num();++I){float Y=250+I*60;DrawRect(FLinearColor(.075f,.10f,.08f,.95f),95*S,Y*S,480*S,46*S);Text(Rows[I],112,Y+12,.9f);AddHitBox(FVector2D(95*S,Y*S),FVector2D(480*S,46*S),FName(*FString::FromInt(I)),true);}Text(FString::Printf(TEXT("Sensitivity %.0f%%"),P->Sensitivity*100),650,280);return;}
 if(P->WeaponShown)Text(FString::Printf(TEXT("M1911   %02d / INF"),P->Ammo),W-240,835,.85f);
 if(P->ReloadTime>0)Text(TEXT("RELOADING"),W/2-55,650,.75f);
 if(P->Help||GetWorld()->GetTimeSeconds()<9){DrawRect(FLinearColor(.015f,.025f,.02f,.58f),28*S,28*S,620*S,92*S);Text(TEXT("ASHGATE / FOREST STUDY"),44,40,1.1f);Text(TEXT("WASD  MOVE   SHIFT  RUN   C  CROUCH   SPACE  JUMP"),44,74,.7f);Text(TEXT("LMB  FIRE   RMB  ADS   R  RELOAD   N  INSPECT   F2  HOLSTER   ESC  MENU"),44,97,.65f);}
 if(P->Help)Text(TEXT("F1  TOGGLE CONTROLS / F2  CLEAR SCENERY VIEW"),44,150,.75f);
}
void AForestHUD::NotifyHitBoxClick(FName N){Super::NotifyHitBoxClick(N);Pressed=N;}
void AForestHUD::NotifyHitBoxRelease(FName N){Super::NotifyHitBoxRelease(N);if(Pressed==N)Forest(this)->Action(FCString::Atoi(*N.ToString()));Pressed=NAME_None;}
#if WITH_EDITOR
static FAutoConsoleCommand PIE(TEXT("Forest.PIEVerify"),TEXT("Real PIE verification for the independent forest demo"),FConsoleCommandDelegate::CreateLambda([]{if(GEditor){FRequestPlaySessionParams P;P.WorldType=EPlaySessionWorldType::PlayInEditor;P.GameModeOverride=AForestMode::StaticClass();GEditor->RequestPlaySession(P);}}));
#endif
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl,ForestTrail,"ForestTrail");
