#include "Depot.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Animation/AnimSequence.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/TextureCube.h"
#include "Components/SceneComponent.h"
#include "Components/TextRenderComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/LightComponent.h"
#include "AIController.h"
#include "Components/SkyLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/PostProcessComponent.h"
#include "Engine/Canvas.h"
#include "Engine/DirectionalLight.h"
#include "Engine/SkyLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/TextRenderActor.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Sound/SoundBase.h"
#include "EngineUtils.h"
#include "DrawDebugHelpers.h"
#include "HighResScreenshot.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Containers/Ticker.h"
#include "HAL/IConsoleManager.h"
#include "Modules/ModuleManager.h"
#if WITH_EDITOR
#include "Editor.h"
#include "PlayInEditorDataTypes.h"
#endif

DEFINE_LOG_CATEGORY_STATIC(LogAshgate, Log, All);
static ADepotGameMode* Mode(const UObject* O) { return Cast<ADepotGameMode>(UGameplayStatics::GetGameMode(O)); }
static UStaticMesh* ArtMesh(const TCHAR* Name) { return LoadObject<UStaticMesh>(nullptr,*FString::Printf(TEXT("/Game/Art/Meshes/%s.%s"),Name,Name)); }
static UMaterialInterface* Mat(const TCHAR* Name) { return LoadObject<UMaterialInterface>(nullptr,*FString::Printf(TEXT("/Game/Art/Materials/%s.%s"),Name,Name)); }
static const TArray<FString> LootTypes = {TEXT("Electronics"),TEXT("Tools"),TEXT("Machine parts"),TEXT("Cable"),TEXT("Medical supplies")};

ADepotPlayer::ADepotPlayer() {
    PrimaryActorTick.bCanEverTick=true; PrimaryActorTick.bTickEvenWhenPaused=true;
    GetCapsuleComponent()->InitCapsuleSize(30,88);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
    bUseControllerRotationYaw=true;
    GetCharacterMovement()->MaxWalkSpeed=340; GetCharacterMovement()->JumpZVelocity=440;
    Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("Eyes")); Camera->SetupAttachment(GetCapsuleComponent());
    Camera->SetRelativeLocation(FVector(0,0,72)); Camera->bUsePawnControlRotation=true; Camera->FieldOfView=94;
    Weapon=CreateDefaultSubobject<USceneComponent>(TEXT("Viewmodel")); Weapon->SetupAttachment(Camera);
    // Imported glTF has -Y forward after Y/Z conversion. Rotate +90 degrees to UE +X.
    Weapon->SetRelativeLocation(FVector(34,15,-12)); Weapon->SetRelativeRotation(FRotator(0,90,0));
    for (const TCHAR* Part : {TEXT("m1911_frame"),TEXT("m1911_slide"),TEXT("m1911_magazine"),TEXT("fps_hands_right"),TEXT("fps_hands_left")}) {
        auto* C=CreateDefaultSubobject<UStaticMeshComponent>(Part); C->SetupAttachment(Weapon); C->SetCollisionEnabled(ECollisionEnabled::NoCollision); C->CastShadow=false;
        if (FString(Part)==TEXT("m1911_slide")) Slide=C;
        if (FString(Part)==TEXT("m1911_magazine")) Magazine=C;
        if (FString(Part)==TEXT("fps_hands_left")) LeftHand=C;
    }
}
void ADepotPlayer::BeginPlay() {
    Super::BeginPlay();
    TArray<UStaticMeshComponent*> Parts; GetComponents(Parts);
    for (auto* C:Parts) C->SetStaticMesh(ArtMesh(*C->GetName()));
    ShotSound=LoadObject<USoundBase>(nullptr,TEXT("/Game/Art/Audio/pistol_shot.pistol_shot"));
    ReloadSound=LoadObject<USoundBase>(nullptr,TEXT("/Game/Art/Audio/reload.reload"));
    EmptySound=LoadObject<USoundBase>(nullptr,TEXT("/Game/Art/Audio/empty.empty"));
}
void ADepotPlayer::SetupPlayerInputComponent(UInputComponent* I) {
    Super::SetupPlayerInputComponent(I);
    I->BindAxisKey(EKeys::MouseX,this,&ADepotPlayer::Yaw); I->BindAxisKey(EKeys::MouseY,this,&ADepotPlayer::Pitch);
    I->BindKey(EKeys::SpaceBar,IE_Pressed,this,&ADepotPlayer::JumpPressed);
    I->BindKey(EKeys::LeftShift,IE_Pressed,this,&ADepotPlayer::Sprint); I->BindKey(EKeys::LeftShift,IE_Released,this,&ADepotPlayer::StopSprint);
    I->BindKey(EKeys::LeftMouseButton,IE_Pressed,this,&ADepotPlayer::Fire).bExecuteWhenPaused=true;
    I->BindKey(EKeys::RightMouseButton,IE_Pressed,this,&ADepotPlayer::Aim); I->BindKey(EKeys::RightMouseButton,IE_Released,this,&ADepotPlayer::UnAim);
    I->BindKey(EKeys::R,IE_Pressed,this,&ADepotPlayer::Reload); I->BindKey(EKeys::N,IE_Pressed,this,&ADepotPlayer::Inspect);
    I->BindKey(EKeys::E,IE_Pressed,this,&ADepotPlayer::Interact); I->BindKey(EKeys::Tab,IE_Pressed,this,&ADepotPlayer::Bag);
    I->BindKey(EKeys::Four,IE_Pressed,this,&ADepotPlayer::Heal);
    I->BindKey(EKeys::Escape,IE_Pressed,this,&ADepotPlayer::Escape).bExecuteWhenPaused=true;
    I->BindKey(EKeys::T,IE_Pressed,this,&ADepotPlayer::PracticeReset);
    if(FParse::Param(FCommandLine::Get(),TEXT("AshgateInputProbe"))) I->BindKey(EKeys::F9,IE_Pressed,this,&ADepotPlayer::CaptureProbe).bExecuteWhenPaused=true;
}
void ADepotPlayer::CaptureProbe() {
    auto* M=Mode(this); if(!M) return;
    UE_LOG(LogAshgate,Display,TEXT("INPUT PROBE phase=%s position=%s ammo=%d reserve=%d aiming=%d inspect=%.2f reload=%.2f bag=%d paused=%d sensitivity=%.2f"),*M->Phase,*GetActorLocation().ToString(),Ammo,Reserve,Aiming,InspectTime,ReloadTime,M->BagOpen,M->Paused,M->Profile->Sensitivity);
    FScreenshotRequest::RequestScreenshot(FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Screenshots/Input.png")),true,true);
}
bool ADepotPlayer::CanAct() const { auto* M=Mode(this); return M && M->Phase==TEXT("raid") && !M->Paused && !M->BagOpen && Health>0; }
void ADepotPlayer::Forward(float V) { if(CanAct()) AddMovementInput(FRotationMatrix(FRotator(0,GetControlRotation().Yaw,0)).GetUnitAxis(EAxis::X),V); }
void ADepotPlayer::Right(float V) { if(CanAct()) AddMovementInput(FRotationMatrix(FRotator(0,GetControlRotation().Yaw,0)).GetUnitAxis(EAxis::Y),V); }
void ADepotPlayer::Yaw(float V) { if(CanAct()) AddControllerYawInput(V*Mode(this)->Profile->Sensitivity); }
void ADepotPlayer::Pitch(float V) { if(CanAct()) AddControllerPitchInput(-V*Mode(this)->Profile->Sensitivity); }
void ADepotPlayer::JumpPressed() { if(CanAct()) Jump(); }
void ADepotPlayer::Sprint() { Running=true; } void ADepotPlayer::StopSprint() { Running=false; }
void ADepotPlayer::Aim() { if(CanAct()) { InspectTime=0; Aiming=true; } } void ADepotPlayer::UnAim() { Aiming=false; }
void ADepotPlayer::Inspect() { if(CanAct() && ReloadTime<=0 && HealTime<=0) { Aiming=false; InspectTime=4.2f; } }
void ADepotPlayer::Reload() {
    if(!CanAct()) return;
    InspectTime=0;
    if(Ammo>=7 || ReloadTime>0 || (Reserve<=0&&!Mode(this)->Practice)) return;
    Aiming=false; HealTime=0; ReloadTime=1.35f; UGameplayStatics::PlaySound2D(this,ReloadSound);
}
void ADepotPlayer::Fire() {
    auto* M=Mode(this); auto* PC=Cast<APlayerController>(Controller);
    if(!M) return;
    if(M->Phase!=TEXT("raid") || M->Paused) {
        float X=0,Y=0; if(PC && PC->GetMousePosition(X,Y)) if(auto* H=Cast<ADepotHUD>(PC->GetHUD())) H->Click(X,Y); return;
    }
    if(!CanAct()) return;
    InspectTime=0;
    if(Cooldown>0 || ReloadTime>0 || HealTime>0) return;
    if(Ammo<=0) { UGameplayStatics::PlaySound2D(this,EmptySound); return; }
    --Ammo; Cooldown=.18f; Kick=1; AddControllerPitchInput(-.65f);
    UGameplayStatics::PlaySound2D(this,ShotSound);
    FVector Start=Camera->GetComponentLocation(), End=Start+Camera->GetForwardVector()*15000;
    FCollisionQueryParams Params; Params.AddIgnoredActor(this); FHitResult Hit;
    bool Blocked=GetWorld()->LineTraceSingleByChannel(Hit,Start,End,ECC_Visibility,Params);
    if(Blocked) { if(auto* G=Cast<ADepotGuard>(Hit.GetActor())) G->Hit(42); DrawDebugPoint(GetWorld(),Hit.ImpactPoint,6,FColor(220,190,130),false,.12f); }
    const FVector Muzzle=Weapon->GetComponentTransform().TransformPosition(FVector(0,-19.6f,.4f));
    DrawDebugLine(GetWorld(),Muzzle,Blocked?Hit.ImpactPoint:End,FColor(220,180,100),false,.045f,0,.3f);
    for(auto G:M->Guards) if(G&&!G->Dead && FVector::Dist(G->GetActorLocation(),GetActorLocation())<3500) { G->Goal=GetActorLocation(); G->Awareness=8; }
}
void ADepotPlayer::Heal() {
    if(!CanAct()) return; InspectTime=0; Aiming=false;
    if(HealTime>0) { HealTime=0; return; }
    if(Kits>0 && (Health<100 || Bleeding) && ReloadTime<=0) HealTime=2.4f;
}
void ADepotPlayer::Hurt(float Damage) {
    if(Health<=0 || Mode(this)->Phase!=TEXT("raid")) return;
    Health=FMath::Max(0.f,Health-Damage); HealTime=0; InspectTime=0; Bleeding=true;
    if(Health<=0) Mode(this)->FinishRaid(false,TEXT("Killed in action - carried equipment lost"));
}
void ADepotPlayer::Interact() { if(CanAct()) Mode(this)->Use(); }
void ADepotPlayer::Bag() { auto* M=Mode(this); if(M&&M->Phase==TEXT("raid")&&!M->Paused) { M->BagOpen=!M->BagOpen; Aiming=false; InspectTime=0; } }
void ADepotPlayer::Escape() {
    auto* M=Mode(this); if(!M) return;
    if(M->BagOpen) { M->BagOpen=false; return; }
    if(M->Phase==TEXT("raid")) M->Pause(!M->Paused);
}
void ADepotPlayer::PracticeReset() { if(Mode(this)->Practice) { ResetLoadout(35,1); Mode(this)->Notice(TEXT("Practice loadout reset")); } }
void ADepotPlayer::ResetLoadout(int32 TotalRounds,int32 Meds) {
    Ammo=FMath::Min(7,TotalRounds); Reserve=TotalRounds-Ammo; Kits=Meds; Health=100; Stamina=100; Bleeding=false;
    HealTime=ReloadTime=InspectTime=Kick=Cooldown=0; Aiming=Running=false;
}
void ADepotPlayer::Tick(float D) {
    Super::Tick(D); auto* M=Mode(this); auto* PC=Cast<APlayerController>(Controller); if(!M||!PC) return;
    if(CanAct()) {
        Forward((PC->IsInputKeyDown(EKeys::W)||PC->IsInputKeyDown(EKeys::Up)?1.f:0.f)-(PC->IsInputKeyDown(EKeys::S)||PC->IsInputKeyDown(EKeys::Down)?1.f:0.f));
        Right((PC->IsInputKeyDown(EKeys::D)||PC->IsInputKeyDown(EKeys::Right)?1.f:0.f)-(PC->IsInputKeyDown(EKeys::A)||PC->IsInputKeyDown(EKeys::Left)?1.f:0.f));
    }
    if(M->Paused) return;
    const bool Sprinting=CanAct()&&Running&&Stamina>1&&!Aiming&&GetVelocity().Size2D()>10;
    Stamina=FMath::Clamp(Stamina+(Sprinting?-20.f:13.f)*D,0.f,100.f);
    GetCharacterMovement()->MaxWalkSpeed=Sprinting?560:(Aiming?200:340);
    Cooldown=FMath::Max(0.f,Cooldown-D); Kick=FMath::FInterpTo(Kick,0.f,D,15);
    if(ReloadTime>0) { ReloadTime-=D; if(ReloadTime<=0) { int32 N=M->Practice?7-Ammo:FMath::Min(7-Ammo,Reserve); Ammo+=N; if(!M->Practice) Reserve-=N; } }
    if(HealTime>0) { HealTime-=D; if(HealTime<=0) { Health=FMath::Min(100.f,Health+45); Bleeding=false; --Kits; M->Notice(TEXT("Treated +45 HP / bleeding stopped")); } }
    if(Bleeding&&M->Phase==TEXT("raid")) { Health=FMath::Max(0.f,Health-D*.6f); if(Health<=0) M->FinishRaid(false,TEXT("Bled out - carried equipment lost")); }
    InspectTime=FMath::Max(0.f,InspectTime-D);
    FVector P=Aiming?FVector(25,0,-2.9f):FVector(34,15,-12);
    FRotator R(0,90,0);
    if(InspectTime>0) { float T=(4.2f-InspectTime)/4.2f; float Envelope=FMath::Sin(PI*T); P+=FVector(-8,-11,10)*Envelope; R+=FRotator(-12*Envelope,75*FMath::Sin(2*PI*T),-20*Envelope); }
    if(ReloadTime>0) { float T=(1.35f-ReloadTime)/1.35f; R.Roll-=30*FMath::Sin(PI*T); P.Z-=5*FMath::Sin(PI*T); }
    if(HealTime>0) P.Z-=22;
    const float Speed=GetVelocity().Size2D(); float Bob=FMath::Sin(GetWorld()->GetTimeSeconds()*(Sprinting?13:8))*FMath::Min(1.f,Speed/340);
    P.Z+=Bob*(Aiming?.1f:.35f); P.X-=Kick*1.5f;
    Weapon->SetRelativeLocation(FMath::VInterpTo(Weapon->GetRelativeLocation(),P,D,12)); Weapon->SetRelativeRotation(FMath::RInterpTo(Weapon->GetRelativeRotation(),R,D,13));
    Slide->SetRelativeLocation(FVector(0,2.8f*(Ammo==0?1:Kick),0));
    Magazine->SetRelativeLocation(FVector(0,0,ReloadTime>0?-12*FMath::Sin(PI*(1.35f-ReloadTime)/1.35f):0));
    if(LeftHand) LeftHand->SetRelativeLocation(FVector(0,0,ReloadTime>0?-7*FMath::Sin(PI*(1.35f-ReloadTime)/1.35f):0));
    Camera->SetFieldOfView(FMath::FInterpTo(Camera->FieldOfView,Aiming?72.f:94.f,D,12));
    Weapon->SetVisibility(M->Phase==TEXT("raid"),true);
}

ADepotGuard::ADepotGuard() {
    AIControllerClass=AAIController::StaticClass();
    PrimaryActorTick.bCanEverTick=true; GetCapsuleComponent()->InitCapsuleSize(32,86);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
    GetCharacterMovement()->MaxWalkSpeed=175; bUseControllerRotationYaw=false;
    auto* Body=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("GuardBody")); Body->SetupAttachment(GetCapsuleComponent());
    Body->SetRelativeLocation(FVector(0,0,-86)); Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}
void ADepotGuard::BeginPlay() {
    Super::BeginPlay(); Home=Goal=GetActorLocation(); SpawnDefaultController();
    auto* Body=FindComponentByClass<UStaticMeshComponent>();
    if(auto* Skel=LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/Art/Characters/Guard.Guard"))) {
        GetMesh()->SetSkeletalMeshAsset(Skel); GetMesh()->SetRelativeLocation(FVector(0,0,-86));
        GetMesh()->SetRelativeRotation(FRotator(0,90,0)); GetMesh()->SetRelativeScale3D(FVector(.85f));
        GetMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        GetMesh()->PlayAnimation(LoadObject<UAnimSequence>(nullptr,TEXT("/Game/Art/Characters/aim_idle.aim_idle")),true);
    } else { Body->SetStaticMesh(ArtMesh(TEXT("enemy"))); Body->SetRelativeScale3D(FVector(.85f)); }
    Sidearm=NewObject<USceneComponent>(this,TEXT("GuardSidearm")); Sidearm->RegisterComponent(); Sidearm->AttachToComponent(GetMesh(),FAttachmentTransformRules::SnapToTargetNotIncludingScale,TEXT("RightHand"));
    for(const TCHAR* Part:{TEXT("m1911_frame"),TEXT("m1911_slide"),TEXT("m1911_magazine")}) {
        auto* C=NewObject<UStaticMeshComponent>(this); C->SetStaticMesh(ArtMesh(Part)); C->SetCollisionEnabled(ECollisionEnabled::NoCollision); C->RegisterComponent(); C->AttachToComponent(Sidearm,FAttachmentTransformRules::KeepRelativeTransform);
    }
}
void ADepotGuard::Hit(float Damage) {
    if(Dead) return; Health-=Damage;
    if(Health<=0) { Dead=true; GetCharacterMovement()->StopMovementImmediately(); GetMesh()->PlayAnimation(LoadObject<UAnimSequence>(nullptr,TEXT("/Game/Art/Characters/death.death")),false); Mode(this)->Notice(TEXT("Guard down - E to recover supplies")); }
    else { Awareness=10; Goal=Mode(this)->Player()->GetActorLocation(); }
}
void ADepotGuard::Tick(float D) {
    Super::Tick(D); auto* M=Mode(this); if(!M || M->Phase!=TEXT("raid") || M->Practice || Dead) return;
    auto* P=M->Player(); if(!P) return;
    ShotTimer-=D; Awareness=FMath::Max(0.f,Awareness-D); Phase+=D;
    const FVector Eye=GetActorLocation()+FVector(0,0,62), Target=P->Camera->GetComponentLocation();
    float Distance=FVector::Dist(Eye,Target); FHitResult H; FCollisionQueryParams Q; Q.AddIgnoredActor(this);
    bool InView=FVector::DotProduct(GetActorForwardVector(),(Target-Eye).GetSafeNormal())>.15f || Awareness>0;
    bool Visible=InView && Distance<2800 && GetWorld()->LineTraceSingleByChannel(H,Eye,Target,ECC_Visibility,Q) && H.GetActor()==P;
    if(Visible) { Goal=P->GetActorLocation(); Awareness=7; }
    if(Awareness<=0) Goal=Home+FVector(FMath::Sin(Phase*.18f)*450,FMath::Cos(Phase*.18f)*300,0);
    FVector Dir=Goal-GetActorLocation(); Dir.Z=0;
    if(Dir.Size()> (Visible?1100:80)) {
        GetCharacterMovement()->MaxWalkSpeed=Awareness>0?270:175;
        FVector Move=Dir.GetSafeNormal(); FHitResult Obstacle;
        if(GetWorld()->LineTraceSingleByChannel(Obstacle,GetActorLocation(),GetActorLocation()+Move*130,ECC_Visibility,Q) && Obstacle.GetActor()!=P) {
            FVector Tangent=FVector::CrossProduct(Obstacle.ImpactNormal,FVector::UpVector).GetSafeNormal();
            if(FVector::DotProduct(Tangent,Move)<0) Tangent=-Tangent; Move=(Tangent+Obstacle.ImpactNormal*.35f).GetSafeNormal();
        }
        AddMovementInput(Move);
    }
    if(!Dir.IsNearlyZero()) SetActorRotation(FRotator(0,Dir.Rotation().Yaw,0));
    if(Sidearm) { Sidearm->SetWorldLocation(GetMesh()->GetSocketLocation(TEXT("RightHand"))-GetActorForwardVector()*3+FVector(0,0,5)); Sidearm->SetWorldRotation(FRotator(0,GetActorRotation().Yaw+90,0)); Sidearm->SetWorldScale3D(FVector(1)); }
    const FName Clip=GetVelocity().Size2D()>25?TEXT("aim_walk"):TEXT("aim_idle");
    if(!Tags.Contains(Clip)) {
        Tags.Remove(TEXT("aim_walk")); Tags.Remove(TEXT("aim_idle")); Tags.Add(Clip);
        const FString Asset=FString::Printf(TEXT("/Game/Art/Characters/%s.%s"),*Clip.ToString(),*Clip.ToString());
        GetMesh()->PlayAnimation(LoadObject<UAnimSequence>(nullptr,*Asset),true);
    }
    if(Visible && Distance<2000 && ShotTimer<=0) {
        ShotTimer=1.25f; DrawDebugLine(GetWorld(),Eye,Target,FColor(200,120,50),false,.08f,0,.5f);
        if(FMath::FRand()<.52f) P->Hurt(11);
    }
}

ADepotGameMode::ADepotGameMode() { DefaultPawnClass=ADepotPlayer::StaticClass(); HUDClass=ADepotHUD::StaticClass(); PrimaryActorTick.bCanEverTick=true; }
ADepotPlayer* ADepotGameMode::Player() const { return Cast<ADepotPlayer>(UGameplayStatics::GetPlayerPawn(this,0)); }
void ADepotGameMode::BeginPlay() {
    Super::BeginPlay(); QA=FParse::Param(FCommandLine::Get(),TEXT("AshgateSmoke"));
    const bool TestProfile=QA||FParse::Param(FCommandLine::Get(),TEXT("AshgateInputProbe"));
    Slot=TestProfile?TEXT("AshgateUE5_QA"):TEXT("AshgateUE5_Profile_v1");
    Profile=Cast<UDepotProfile>(UGameplayStatics::LoadGameFromSlot(Slot,0));
    if(!Profile||TestProfile) Profile=Cast<UDepotProfile>(UGameplayStatics::CreateSaveGameObject(UDepotProfile::StaticClass()));
    if(Profile->ActiveRaid) { Profile->ActiveRaid=false; Notice(TEXT("Previous raid abandoned - carried equipment already deducted")); Save(); }
    BuildDepot(); Pause(false);
    if(auto* PC=UGameplayStatics::GetPlayerController(this,0)) PC->ConsoleCommand(FString::Printf(TEXT("scalability %d"),Profile->Quality));
    if(auto* P=Player()) { P->SetActorLocation(FVector(-3900,-3300,100)); if(P->Controller) P->Controller->SetControlRotation(FRotator(0,36,0)); }
    UE_LOG(LogAshgate,Display,TEXT("READY: 96x88m depot, %d cases, %d guards; save slot %s; world type %d"),Cases.Num(),Guards.Num(),*Slot,int32(GetWorld()->WorldType));
}
void ADepotGameMode::Save() {
    SaveHealthy=UGameplayStatics::SaveGameToSlot(Profile,Slot,0);
    if(!SaveHealthy) { Message=TEXT("SAVE FAILED - do not deploy until storage is writable"); MessageTime=999; UE_LOG(LogAshgate,Error,TEXT("Save failed: %s"),*Slot); }
}
void ADepotGameMode::Notice(const FString& T) { Message=T; MessageTime=6; }
int32 ADepotGameMode::ValueOf(const FString& I) const { return I==TEXT("Electronics")?180:I==TEXT("Tools")?120:I==TEXT("Machine parts")?140:I==TEXT("Cable")?65:90; }
void ADepotGameMode::Pause(bool V) {
    Paused=V; UGameplayStatics::SetGamePaused(this,V);
    if(auto* PC=UGameplayStatics::GetPlayerController(this,0)) {
        bool Menu=V||Phase!=TEXT("raid"); PC->bShowMouseCursor=Menu;
        if(Menu) { FInputModeGameAndUI Input; Input.SetHideCursorDuringCapture(false); PC->SetInputMode(Input); }
        else { PC->SetInputMode(FInputModeGameOnly()); }
    }
    if(auto* P=Player()) { P->Aiming=false; P->Running=false; }
}
void ADepotGameMode::StartRaid(bool IsPractice) {
    if(Phase==TEXT("raid")) return;
    auto* P=Player(); if(!P) return;
    int32 R=35,K=1;
    if(!IsPractice) {
        if(Profile->Guns<1 || Profile->Rounds<7) {
            if(Profile->Credits>=350) { Notice(TEXT("Buy a weapon or ammunition before deploying")); return; }
            Profile->Guns=FMath::Max(Profile->Guns,1); Profile->Rounds=FMath::Max(Profile->Rounds,21); Notice(TEXT("Emergency redeployment kit issued"));
        }
        UDepotProfile* Before=DuplicateObject<UDepotProfile>(Profile,this);
        R=FMath::Min(35,Profile->Rounds); K=FMath::Min(1,Profile->Kits);
        --Profile->Guns; Profile->Rounds-=R; Profile->Kits-=K; Profile->ActiveRaid=true; Save();
        if(!SaveHealthy) { Profile=Before; return; }
    }
    Practice=IsPractice; Phase=TEXT("raid"); RaidTime=600; ExtractTime=0; BagItems.Empty(); BagOpen=false;
    P->ResetLoadout(R,K); P->SetActorLocation(FVector(-3900,-3300,100)); P->GetCharacterMovement()->StopMovementImmediately();
    if(P->Controller) P->Controller->SetControlRotation(FRotator(0,36,0));
    for(int32 I=0;I<Guards.Num();++I) { auto G=Guards[I]; G->SetActorLocation(G->Home); G->Health=80; G->Dead=false; G->Awareness=0; G->Tags.Remove(TEXT("Searched")); G->Tags.Remove(TEXT("aim_idle")); G->Tags.Remove(TEXT("aim_walk")); G->SetActorRotation(FRotator::ZeroRotator); G->SetActorHiddenInGame(IsPractice); G->SetActorEnableCollision(!IsPractice); }
    for(int32 I=0;I<Cases.Num();++I) { Cases[I]->SetActorHiddenInGame(false); Cases[I]->SetActorEnableCollision(true); Searched[I]=false; }
    Pause(false); Notice(IsPractice?TEXT("FIRING RANGE - unlimited reserve / T resets loadout"):TEXT("DEPOT 04 - extract through the north-east gate"));
    UE_LOG(LogAshgate,Display,TEXT("DEPLOY practice=%d rounds=%d kits=%d stash=%d/%d/%d active=%d"),Practice,R,K,Profile->Guns,Profile->Rounds,Profile->Kits,Profile->ActiveRaid);
}
void ADepotGameMode::FinishRaid(bool Success,const FString& Reason) {
    if(Phase!=TEXT("raid")) return;
    if(!Practice) {
        if(Success) { ++Profile->Guns; Profile->Rounds+=Player()->Ammo+Player()->Reserve; Profile->Kits+=Player()->Kits; Profile->Credits+=300; for(const auto& I:BagItems) ++Profile->Goods.FindOrAdd(I); }
        Profile->ActiveRaid=false; Save();
    }
    Phase=TEXT("base"); BagOpen=false; ExtractTime=0; Pause(false); Notice(Reason);
    UE_LOG(LogAshgate,Display,TEXT("RETURN success=%d practice=%d reason=%s"),Success,Practice,*Reason);
}
int32 ADepotGameMode::FindCase() const {
    auto* P=Player(); if(!P) return -1;
    FHitResult H; FCollisionQueryParams Q; Q.AddIgnoredActor(P);
    if(!GetWorld()->LineTraceSingleByChannel(H,P->Camera->GetComponentLocation(),P->Camera->GetComponentLocation()+P->Camera->GetForwardVector()*300,ECC_Visibility,Q)) return -1;
    for(int32 I=0;I<Cases.Num();++I) if(Cases[I]==H.GetActor()&&!Searched[I]) return I;
    for(int32 I=0;I<Guards.Num();++I) if(Guards[I]==H.GetActor()&&Guards[I]->Dead&&!Guards[I]->Tags.Contains(TEXT("Searched"))) return Cases.Num()+I;
    return -1;
}
void ADepotGameMode::Use() {
    int32 I=FindCase(); if(I<0) return;
    if(BagItems.Num()>=12) { Notice(TEXT("Bag full (12/12)")); return; }
    FString Item=LootTypes[I%LootTypes.Num()]; BagItems.Add(Item);
    if(I<Cases.Num()) { Searched[I]=true; Cases[I]->SetActorHiddenInGame(true); Cases[I]->SetActorEnableCollision(false); }
    else Guards[I-Cases.Num()]->Tags.Add(TEXT("Searched"));
    Notice(TEXT("Recovered ")+Item);
}
void ADepotGameMode::MenuAction(int32 Row) {
    if(Phase==TEXT("base")) {
        if(Row==0) StartRaid(); else if(Row==1) StartRaid(true);
        else if(Row>=2&&Row<=4) { int32 Cost=Row==2?350:Row==3?70:90; if(Profile->Credits<Cost) Notice(TEXT("Insufficient credits")); else { Profile->Credits-=Cost; if(Row==2) ++Profile->Guns; if(Row==3) Profile->Rounds+=35; if(Row==4) ++Profile->Kits; Save(); } }
        else if(Row==5) { int32 Earned=0; for(auto& P:Profile->Goods) Earned+=ValueOf(P.Key)*P.Value; Profile->Goods.Empty(); Profile->Credits+=Earned; Save(); Notice(FString::Printf(TEXT("Sold recovered goods: +%d CR"),Earned)); }
        else if(Row==6) UGameplayStatics::GetPlayerController(this,0)->ConsoleCommand(TEXT("quit"));
    } else if(Paused) {
        if(Row==0) Pause(false);
        if(Row==1||Row==2) { Profile->Sensitivity=FMath::Clamp(Profile->Sensitivity+(Row==1?-.1f:.1f),.1f,3.f); Save(); }
        if(Row==3) { Profile->Quality=(Profile->Quality+1)%4; UGameplayStatics::GetPlayerController(this,0)->ConsoleCommand(FString::Printf(TEXT("scalability %d"),Profile->Quality)); Save(); }
        if(Row==4) { Pause(false); FinishRaid(false,Practice?TEXT("Practice complete"):TEXT("Raid abandoned - carried equipment lost")); }
    }
}
void ADepotGameMode::Tick(float D) {
    Super::Tick(D); if(QA) QATick(D);
    if(MessageTime>0) MessageTime-=D;
    if(Phase!=TEXT("raid")||Paused) return;
    if(!Practice) {
        RaidTime-=D; if(RaidTime<=0) { FinishRaid(false,TEXT("Time expired - carried equipment lost")); return; }
        FVector Delta=Player()->GetActorLocation()-Extraction; Delta.Z=0;
        if(Delta.Size()<240) { ExtractTime+=D; if(ExtractTime>=6) FinishRaid(true,TEXT("EXTRACTED / +300 CR / equipment secured")); } else ExtractTime=0;
    }
    Focus=FindCase()>=0?TEXT("[E] Recover supplies"):TEXT("");
}

void ADepotGameMode::BuildDepot() {
    auto Box=[&](FString Name,FVector Pos,FVector Size,const TCHAR* Material,FLinearColor Tint=FLinearColor::White) {
        auto* A=GetWorld()->SpawnActor<AStaticMeshActor>(Pos,FRotator::ZeroRotator);
        auto* C=A->GetStaticMeshComponent(); C->SetMobility(EComponentMobility::Movable); C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube"))); C->SetWorldScale3D(Size/100); C->SetCollisionProfileName(TEXT("BlockAll"));
        if(auto* M=Mat(Material)) C->SetMaterial(0,M);
        return A;
    };
    auto Prop=[&](const TCHAR* Name,FVector Pos,float Yaw=0.f,float Scale=1.f) {
        auto* A=GetWorld()->SpawnActor<AStaticMeshActor>(Pos,FRotator(0,Yaw,0)); auto* C=A->GetStaticMeshComponent(); C->SetMobility(EComponentMobility::Movable); C->SetStaticMesh(ArtMesh(Name)); C->SetWorldScale3D(FVector(Scale)); C->SetCollisionProfileName(TEXT("BlockAll")); return A;
    };
    auto Sign=[&](const FString& Text,FVector Pos,float Yaw,float Size,FColor Color) {
        auto* A=GetWorld()->SpawnActor<ATextRenderActor>(Pos,FRotator(0,Yaw,0)); auto* C=A->GetTextRender(); C->SetText(FText::FromString(Text)); C->SetWorldSize(Size); C->SetTextRenderColor(Color); C->SetHorizontalAlignment(EHTA_Center);
    };
    Box(TEXT("Depot slab"),FVector(0,0,-25),FVector(9600,8800,50),TEXT("asphalt"));
    for(int32 Side:{-1,1}) { Box(TEXT("Perimeter"),FVector(Side*4800,0,170),FVector(32,8800,340),TEXT("concrete")); Box(TEXT("Perimeter"),FVector(0,Side*4400,170),FVector(9600,32,340),TEXT("concrete")); }
    // Warehouse shell with two open gates, structural columns and roof lights.
    Box(TEXT("Warehouse floor"),FVector(0,0,5),FVector(3100,2600,10),TEXT("concrete"));
    for(int32 Side:{-1,1}) {
        Box(TEXT("Warehouse side"),FVector(0,Side*1300,280),FVector(3100,24,560),TEXT("brick"));
        for(int32 End:{-1,1}) Box(TEXT("Gate pier"),FVector(Side*1550,End*925,280),FVector(24,750,560),TEXT("corrugated"));
        Box(TEXT("Gate lintel"),FVector(Side*1550,0,490),FVector(24,1100,140),TEXT("corrugated"));
    }
    Box(TEXT("Warehouse roof"),FVector(0,0,580),FVector(3300,2800,28),TEXT("corrugated"));
    for(int32 X=-1;X<=1;++X) for(int32 Y:{-1,1}) { Box(TEXT("Steel column"),FVector(X*1300,Y*1200,280),FVector(26,26,560),TEXT("steel")); Prop(TEXT("lamp"),FVector(X*1000,Y*650,520)); }
    // Office / workshop shells, open doorways.
    for(FVector Center:{FVector(800,-2850,0),FVector(-2950,1800,0)}) {
        Box(TEXT("Annex rear"),Center+FVector(0,650,180),FVector(1700,24,360),TEXT("brick"));
        for(int32 S:{-1,1}) Box(TEXT("Annex side"),Center+FVector(S*850,0,180),FVector(24,1300,360),TEXT("concrete"));
        for(int32 S:{-1,1}) Box(TEXT("Annex front"),Center+FVector(S*560,-650,180),FVector(580,24,360),TEXT("brick"));
        Box(TEXT("Annex roof"),Center+FVector(0,0,370),FVector(1800,1400,25),TEXT("corrugated"));
    }
    for(int32 I=0;I<4;++I) {
        FVector P(2600+(I%2)*850,-1200+(I/2)*1700,135);
        Box(TEXT("Cargo container"),P,FVector(650,250,270),TEXT("corrugated"));
        for(int32 J=-3;J<=3;++J) Box(TEXT("Container ribs"),P+FVector(J*85,130,0),FVector(12,12,260),TEXT("steel"));
    }
    for(int32 I=0;I<10;++I) { FVector P(-2600+(I%5)*1050,-1900+(I/5)*4200,0); Prop(TEXT("barrier"),P,90); Prop(TEXT("barrel"),P+FVector(160,100,0)); }
    Prop(TEXT("generator"),FVector(-1800,-900,0),30); Prop(TEXT("pipes"),FVector(200,1150,50),90);
    for(int32 I=0;I<14;++I) { FVector P(-1000+(I%4)*620,-650+(I/4)*430,0); if(I%3!=1) Prop(TEXT("crate"),P,I*31); }
    const TArray<FVector> Locations={FVector(-3550,-2800,0),FVector(-2400,-1000,0),FVector(-900,-800,0),FVector(700,-750,0),FVector(1100,750,0),FVector(-1100,850,0),FVector(200,-3100,0),FVector(1200,-2800,0),FVector(-3200,1700,0),FVector(-2700,2000,0),FVector(2850,-600,0),FVector(3500,2000,0),FVector(1900,3300,0)};
    for(auto P:Locations) { auto* A=Prop(TEXT("crate"),P); A->Tags.Add(TEXT("LootCase")); Cases.Add(A); Searched.Add(false); }
    for(int32 I=0;I<8;++I) { FVector P(-1800+(I%4)*1300,400+(I/4)*2300,100); auto* G=GetWorld()->SpawnActor<ADepotGuard>(P,FRotator::ZeroRotator); Guards.Add(G); }
    Box(TEXT("Extraction marker"),Extraction+FVector(0,0,2),FVector(450,450,4),TEXT("extract"));
    for(int32 S:{-1,1}) Box(TEXT("Extraction gate"),Extraction+FVector(S*275,180,190),FVector(30,40,380),TEXT("extract"));
    Box(TEXT("Extraction lintel"),Extraction+FVector(0,180,390),FVector(580,40,30),TEXT("extract"));
    Sign(TEXT("DEPOT 04"),FVector(-1580,0,440),180,90,FColor(220,210,177));
    Sign(TEXT("EXTRACTION  /  6 SEC"),Extraction+FVector(0,150,320),-90,36,FColor(110,255,180));
    Sign(TEXT("RESTRICTED INDUSTRIAL AREA"),FVector(-4200,-3000,200),0,28,FColor(230,190,100));
    auto* Sun=GetWorld()->SpawnActor<ADirectionalLight>(FVector(0,0,1000),FRotator(-32,-28,0));
    Cast<UDirectionalLightComponent>(Sun->GetLightComponent())->bAtmosphereSunLight=true;
    Sun->GetLightComponent()->SetMobility(EComponentMobility::Movable); Sun->GetLightComponent()->SetIntensity(3.5f); Sun->GetLightComponent()->SetLightColor(FLinearColor(1,.88f,.72f));
    auto* Sky=GetWorld()->SpawnActor<ASkyLight>(); Sky->GetLightComponent()->SetMobility(EComponentMobility::Movable); Sky->GetLightComponent()->SetIntensity(1.2f);
    Sky->GetLightComponent()->SourceType=SLS_SpecifiedCubemap; Sky->GetLightComponent()->SetCubemap(LoadObject<UTextureCube>(nullptr,TEXT("/Engine/MapTemplates/Sky/DaylightAmbientCubemap.DaylightAmbientCubemap"))); Sky->GetLightComponent()->SetRealTimeCaptureEnabled(false);
    AActor* Atmos=GetWorld()->SpawnActor<AActor>(); auto* Atmosphere=NewObject<USceneComponent>(Atmos); Atmos->SetRootComponent(Atmosphere); Atmosphere->RegisterComponent();
    // Engine's sky atmosphere actor is spawned by the authored map; fog and exposure are local to this world.
    auto* Fog=GetWorld()->SpawnActor<AExponentialHeightFog>(); Fog->GetComponent()->SetFogDensity(.012f); Fog->GetComponent()->SetFogHeightFalloff(.25f);
    auto* Post=NewObject<UPostProcessComponent>(Atmos); Post->RegisterComponent(); Post->bUnbound=true;
    auto& S=Post->Settings; S.bOverride_AutoExposureMinBrightness=true; S.bOverride_AutoExposureMaxBrightness=true; S.AutoExposureMinBrightness=0; S.AutoExposureMaxBrightness=2;
    S.bOverride_BloomIntensity=true; S.BloomIntensity=.12f; S.bOverride_MotionBlurAmount=true; S.MotionBlurAmount=.12f;
    S.bOverride_VignetteIntensity=true; S.VignetteIntensity=.2f;
}

void ADepotHUD::Panel(float X,float Y,float W,float H,FLinearColor Color) { DrawRect(Color,X*Scale,Y*Scale,W*Scale,H*Scale); }
void ADepotHUD::Text(const FString& V,float X,float Y,float Size,FLinearColor Color) { DrawText(V,Color,X*Scale,Y*Scale,GEngine->GetMediumFont(),Size*Scale,false); }
void ADepotHUD::DrawHUD() {
    Super::DrawHUD(); auto* M=Mode(this); if(!Canvas||!M||!M->Player()) return;
    Scale=Canvas->SizeY/900.f; float W=Canvas->SizeX/Scale; auto* P=M->Player(); FLinearColor Accent(.68f,.83f,.66f);
    if(M->Phase==TEXT("base")||M->Paused) {
        Panel(0,0,W,900,FLinearColor(.015f,.022f,.025f,.86f)); Panel(65,75,4,70,Accent);
        Text(TEXT("ASHGATE"),92,68,2.5f); Text(TEXT("DEPOT 04  /  SOLO EXTRACTION"),95,125,.95f,Accent);
        Text(M->Paused?TEXT("PAUSED / FIELD SETTINGS"):TEXT("OPERATIONS / SECURE STASH"),95,195,1.1f);
        TArray<FString> Rows=M->Paused?TArray<FString>{TEXT("RESUME"),TEXT("SENSITIVITY  -"),TEXT("SENSITIVITY  +"),TEXT("GRAPHICS QUALITY  / CYCLE"),M->Practice?TEXT("RETURN TO BASE"):TEXT("ABANDON RAID / LOSE CARRIED ITEMS")}:
            TArray<FString>{TEXT("DEPLOY TO DEPOT 04"),TEXT("FIRING RANGE"),TEXT("BUY M1911                         350 CR"),TEXT("BUY 35 ROUNDS                      70 CR"),TEXT("BUY MEDICAL KIT                    90 CR"),TEXT("SELL RECOVERED GOODS"),TEXT("QUIT TO DESKTOP")};
        for(int32 I=0;I<Rows.Num();++I) { Panel(95,250+I*57,490,46,FLinearColor(.07f,.09f,.09f,.95f)); Text(Rows[I],112,260+I*57,.9f); }
        if(M->Paused) { Text(FString::Printf(TEXT("Mouse sensitivity: %.0f%% / quality: %d"),M->Profile->Sensitivity*100,M->Profile->Quality),650,260,1,Accent); Text(TEXT("Settings save automatically. Esc resumes."),650,310,.85f); }
        else {
            Text(FString::Printf(TEXT("%d CR"),M->Profile->Credits),650,250,2,Accent);
            Text(FString::Printf(TEXT("M1911  %d     ROUNDS  %d     MED KITS  %d"),M->Profile->Guns,M->Profile->Rounds,M->Profile->Kits),650,320,1);
            int32 Row=0; for(auto& Pair:M->Profile->Goods) Text(FString::Printf(TEXT("%s x%d"),*Pair.Key,Pair.Value),650,370+Row++*30,.9f);
            Text(TEXT("Explore. Recover. Extract."),650,550,1.3f,Accent);
            Text(TEXT("North-east gate / hold the zone for 6 seconds"),650,600,.85f);
            Text(TEXT("Death, timeout or abandonment loses your loadout."),650,635,.85f);
        }
        Text(TEXT("UE5 PROTOTYPE / M1911 by egorbelous / CC BY 4.0 / full credits bundled"),95,835,.7f,FLinearColor(.6f,.65f,.65f));
    } else {
        Panel(38,35,290,70,FLinearColor(0,0,0,.55f)); Text(FString(TEXT("DEPOT 04 / "))+(M->Practice?TEXT("PRACTICE"):TEXT("RAID")),52,45,.9f,Accent);
        Text(M->Practice?TEXT("UNLIMITED RESERVE"):FString::Printf(TEXT("%02d:%02d / EXTRACT NORTH-EAST"),int32(M->RaidTime)/60,int32(M->RaidTime)%60),52,76,.8f);
        if(!P->Aiming) { Panel(W/2-2,449,4,2,FLinearColor(.9f,.9f,.85f,.75f)); }
        Panel(38,790,370,75,FLinearColor(0,0,0,.55f)); Text(FString::Printf(TEXT("HP %03.0f    STAMINA %03.0f    KITS %d"),P->Health,P->Stamina,P->Kits),52,805,.9f,P->Bleeding?FLinearColor(1,.35f,.2f):FLinearColor::White);
        Text(P->Bleeding?TEXT("BLEEDING / [4] TREAT"):TEXT("[TAB] BAG   [ESC] SETTINGS"),52,840,.8f);
        Panel(W-310,790,270,75,FLinearColor(0,0,0,.55f)); Text(FString::Printf(TEXT("M1911  %02d / %s"),P->Ammo,M->Practice?TEXT("INF"):*FString::FromInt(P->Reserve)),W-290,802,1.4f); Text(TEXT("[R] RELOAD   [N] INSPECT"),W-290,841,.8f);
        Text(M->Focus,W/2-110,530,.9f,Accent);
        if(P->ReloadTime>0) Text(TEXT("RELOADING"),W/2-60,600,.9f);
        if(P->HealTime>0) Text(FString::Printf(TEXT("TREATING %.1fs"),P->HealTime),W/2-70,600,.9f,Accent);
        if(M->ExtractTime>0) Text(FString::Printf(TEXT("EXTRACTING %.1f / 6.0"),M->ExtractTime),W/2-120,190,1.3f,Accent);
        if(M->BagOpen) { Panel(W/2-250,220,500,480,FLinearColor(.015f,.025f,.025f,.95f)); Text(FString::Printf(TEXT("FIELD BAG  %d / 12"),M->BagItems.Num()),W/2-220,245,1.3f,Accent); for(int32 I=0;I<M->BagItems.Num();++I) Text(FString::Printf(TEXT("%02d   %s"),I+1,*M->BagItems[I]),W/2-220,300+I*27,.9f); Text(TEXT("TIME AND ENEMIES CONTINUE / TAB OR ESC TO CLOSE"),W/2-220,660,.65f); }
        Text(TEXT("WASD MOVE / SHIFT RUN / SPACE JUMP / LMB FIRE / RMB ADS / E RECOVER"),W/2-340,875,.65f,FLinearColor(.7f,.75f,.7f));
    }
    if(M->MessageTime>0) { Panel(75,720,W-150,45,FLinearColor(.02f,.04f,.035f,.9f)); Text(M->Message,95,732,.85f,Accent); }
}
void ADepotHUD::Click(float X,float Y) { auto* M=Mode(this); if(!M||Scale<=0) return; X/=Scale; Y/=Scale; if(X>=95&&X<=585&&Y>=250) { int32 Row=int32((Y-250)/57); if(FMath::Fmod(Y-250,57)<46) M->MenuAction(Row); } }

void ADepotGameMode::Check(bool C,const TCHAR* N) { UE_LOG(LogAshgate,Display,TEXT("QA %s: %s"),C?TEXT("PASS"):TEXT("FAIL"),N); if(!C) ++QAFailures; }
void ADepotGameMode::QATestField() {
    auto* P=Player();
    auto AimAt=[&](FVector Target) { FRotator R=(Target-P->Camera->GetComponentLocation()).Rotation(); P->Controller->SetControlRotation(R); P->Camera->SetWorldRotation(R); };
    FVector CasePos=Cases[0]->GetActorLocation(); P->SetActorLocation(CasePos+FVector(-180,0,100));
    AimAt(Cast<AStaticMeshActor>(Cases[0])->GetStaticMeshComponent()->Bounds.Origin);
    Check(FindCase()==0,TEXT("loot targeting uses a visibility ray")); Use();
    Check(BagItems.Num()==1&&Searched[0],TEXT("E interaction recovers a case once")); Use(); Check(BagItems.Num()==1,TEXT("searched case cannot duplicate items"));
    CasePos=Cases[1]->GetActorLocation(); P->SetActorLocation(CasePos+FVector(-180,0,100)); AimAt(Cast<AStaticMeshActor>(Cases[1])->GetStaticMeshComponent()->Bounds.Origin);
    while(BagItems.Num()<12) BagItems.Add(TEXT("Cable")); Use(); Check(BagItems.Num()==12&&!Searched[1],TEXT("full bag leaves case unconsumed")); BagItems.Empty();
    auto* G=Guards[0].Get(); G->SetActorLocation(FVector(-3500,-3900,100)); P->SetActorLocation(FVector(-4200,-3900,100)); AimAt(G->GetActorLocation()+FVector(0,0,30));
    auto* Block=GetWorld()->SpawnActor<AStaticMeshActor>(FVector(-3850,-3900,130),FRotator::ZeroRotator);
    auto* C=Block->GetStaticMeshComponent(); C->SetMobility(EComponentMobility::Movable); C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube"))); C->SetWorldScale3D(FVector(.5f,2,2.6f)); C->SetCollisionProfileName(TEXT("BlockAll"));
    P->Cooldown=0; P->Fire(); Check(G->Health==80,TEXT("wall blocks hitscan damage"));
    Check(G->Awareness>0&&FVector::Dist(G->Goal,P->GetActorLocation())<1,TEXT("gunshot alerts nearby guard through cover"));
    G->ShotTimer=0; G->Tick(.2f); Check(G->ShotTimer<=0,TEXT("wall blocks guard firing line of sight"));
    Block->SetActorEnableCollision(false); Block->Destroy();
    P->Cooldown=0; P->Fire(); Check(G->Health==38,TEXT("unobstructed hitscan damages guard"));
    G->ShotTimer=0; G->Tick(.2f); Check(G->ShotTimer>0,TEXT("guard fires when player is visible"));
    P->Cooldown=0; P->Fire(); Check(G->Dead,TEXT("guard dies after lethal hits"));
    P->SetActorLocation(G->GetActorLocation()-FVector(180,0,0)); AimAt(G->GetActorLocation()+FVector(0,0,30)); Use();
    Check(BagItems.Num()==1&&G->Tags.Contains(TEXT("Searched")),TEXT("dead guard loot recoverable")); BagItems.Empty();
    P->ResetLoadout(35,1);
}
void ADepotGameMode::QATick(float D) {
    QAElapsed+=D; auto* P=Player(); if(!P||QAElapsed<2) return;
    // Exercises actual ticking world and transaction boundaries using an isolated save slot.
    switch(QAStep) {
    case 0: Check(Cases.Num()==13&&Guards.Num()==8,TEXT("world population")); StartRaid(true); QAPosition=P->GetActorLocation(); ++QAStep; QAElapsed=0; break;
    case 1: P->Forward(1); if(QAElapsed>3) { Check(FVector::Dist(P->GetActorLocation(),QAPosition)>100,TEXT("character movement with world collision")); P->Inspect(); Check(P->InspectTime>0,TEXT("inspect starts")); P->Aim(); Check(P->InspectTime==0&&P->Aiming,TEXT("ADS cancels inspect")); P->UnAim(); P->Fire(); Check(P->Ammo==6,TEXT("single shot consumes one round")); P->Inspect(); P->Reload(); Check(P->InspectTime==0&&P->ReloadTime>0,TEXT("reload cancels inspect")); ++QAStep; QAElapsed=0; } break;
    case 2: Check(P->Ammo==7&&P->ReloadTime<=0,TEXT("reload completes")); P->Health=40; P->Bleeding=true; P->Heal(); P->Hurt(1); Check(P->HealTime==0&&P->Kits==1,TEXT("damage cancels heal without consuming kit")); P->Heal(); ++QAStep; QAElapsed=0; break;
    case 3: if(QAElapsed<3) break; Check(P->Health>80&&!P->Bleeding&&P->Kits==0,TEXT("heal completes and consumes kit")); BagOpen=true; P->Escape(); Check(!BagOpen&&!Paused,TEXT("Esc closes bag without pausing")); FinishRaid(false,TEXT("QA practice complete")); StartRaid(false); Check(Profile->Guns==1&&Profile->Rounds==49&&Profile->Kits==3&&Profile->ActiveRaid,TEXT("deploy debits stash before gameplay")); { auto* Disk=Cast<UDepotProfile>(UGameplayStatics::LoadGameFromSlot(Slot,0)); Check(Disk&&Disk->ActiveRaid&&Disk->Guns==1&&Disk->Rounds==49,TEXT("active raid debit persisted / no restart duplication")); } for(auto G:Guards) G->SetActorTickEnabled(false); QATestField(); P->Bleeding=false; P->SetActorLocation(Extraction+FVector(0,0,100)); ++QAStep; QAElapsed=0; break;
    case 4: if(QAElapsed<3) break; Check(ExtractTime>2&&ExtractTime<6,TEXT("extraction progresses inside zone")); P->SetActorLocation(Extraction+FVector(-600,0,100)); ++QAStep; QAElapsed=0; break;
    case 5: Check(ExtractTime==0,TEXT("leaving zone resets countdown")); BagItems.Add(TEXT("Electronics")); P->SetActorLocation(Extraction+FVector(0,0,100)); ++QAStep; QAElapsed=0; break;
    case 6: if(QAElapsed<7) break; Check(Phase==TEXT("base")&&Profile->Credits==2100&&Profile->Guns==2&&Profile->Rounds==84&&Profile->Goods.FindRef(TEXT("Electronics"))==1&&!Profile->ActiveRaid,TEXT("extraction returns equipment and loot / reward once")); MenuAction(5); Check(Profile->Credits==2280&&Profile->Goods.Num()==0,TEXT("stash sale")); StartRaid(false); FinishRaid(false,TEXT("QA death")); Check(Profile->Guns==1&&Profile->Rounds==49&&Profile->Kits==3&&!Profile->ActiveRaid,TEXT("failed raid loses only carried equipment")); Profile->Sensitivity=1.3f; Save(); { auto* Disk=Cast<UDepotProfile>(UGameplayStatics::LoadGameFromSlot(Slot,0)); Check(Disk&&FMath::IsNearlyEqual(Disk->Sensitivity,1.3f),TEXT("sensitivity persists")); } StartRaid(true); P->SetActorLocation(FVector(-3100,-1800,100)); P->Controller->SetControlRotation(FRotator(-2,26,0)); ++QAStep; QAElapsed=0; break;
    case 7: if(QAElapsed<5) break; { FString File=FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Screenshots/QA-gameplay.png")); FScreenshotRequest::RequestScreenshot(File,false,false); } ++QAStep; QAElapsed=0; break;
    case 8: QASum+=D; QAMax=FMath::Max(QAMax,double(D)); ++QASamples; if(QAElapsed>12) { UE_LOG(LogAshgate,Display,TEXT("QA PERFORMANCE samples=%d mean=%.2fms fps=%.1f worst=%.2fms / viewport-dependent, warm-up excluded"),QASamples,QASum*1000/QASamples,QASamples/QASum,QAMax*1000); P->Inspect(); ++QAStep; QAElapsed=0; } break;
    case 9: if(QAElapsed<2.8) break; FScreenshotRequest::RequestScreenshot(FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Screenshots/QA-inspect.png")),false,false); ++QAStep; QAElapsed=0; break;
    case 10: if(QAElapsed<3) break; UE_LOG(LogAshgate,Display,TEXT("QA COMPLETE failures=%d worldtype=%d"),QAFailures,int32(GetWorld()->WorldType)); ++QAStep;
#if WITH_EDITOR
        if(GetWorld()->WorldType==EWorldType::PIE) { GEditor->RequestEndPlayMap(); FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float) { GEditor->Exec(GEditor->GetEditorWorldContext().World(),TEXT("QUIT_EDITOR")); return false; }),3.f); break; }
#endif
        FPlatformMisc::RequestExitWithStatus(false,QAFailures?1:0); break;
    }
}

#if WITH_EDITOR
static FAutoConsoleCommand PIECommand(TEXT("Ashgate.PIEVerify"),TEXT("Start a real PIE session; -AshgateSmoke uses an isolated save and checks gameplay."),FConsoleCommandDelegate::CreateLambda([] {
    if(GEditor) { FRequestPlaySessionParams Params; Params.WorldType=EPlaySessionWorldType::PlayInEditor; Params.GameModeOverride=ADepotGameMode::StaticClass(); GEditor->RequestPlaySession(Params); }
}));
#endif
IMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl,Ashgate,"Ashgate");
