#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "Forest.generated.h"
class UCameraComponent;class UStaticMeshComponent;class USceneComponent;class USoundBase;class UAudioComponent;class USoundAttenuation;
UCLASS()
class AForestPlayer:public ACharacter {
 GENERATED_BODY()
public:
 AForestPlayer();void EndPlay(const EEndPlayReason::Type Reason) override;void Landed(const FHitResult& Hit) override;void BeginPlay() override;void Tick(float D) override;void SetupPlayerInputComponent(UInputComponent* I) override;
 UPROPERTY() TMap<FName,TObjectPtr<UStaticMesh>> ViewmodelMeshes;
 bool Legacy1911=false;int32 ServiceAmmo=8,LegacyAmmo=7;
 int32 Capacity() const{return Legacy1911?7:8;}void LoadViewmodels();void ApplyViewmodel();void SwitchPistol();
 UPROPERTY() TObjectPtr<UCameraComponent> Camera;
 UPROPERTY() TObjectPtr<USceneComponent> Weapon;
 UPROPERTY() TObjectPtr<UStaticMeshComponent> Slide;
 UPROPERTY() TObjectPtr<UStaticMeshComponent> Magazine;
 UPROPERTY() TObjectPtr<USceneComponent> LeftHand;
 UPROPERTY() TMap<FName,TObjectPtr<USoundBase>> Sounds;
 UPROPERTY() TObjectPtr<UAudioComponent> WindAudio;
 UPROPERTY() TObjectPtr<UAudioComponent> BirdsAudio;
 UPROPERTY() TObjectPtr<USoundAttenuation> GroundAttenuation;
 TMap<FName,int32> SoundEvents;TArray<float> CaseDelays;
 FVector LastFootPosition;float FootDistance=0,ActionSoundCooldown=0;int32 LastShot=-1,FootIndex=0;bool ReloadWasEmpty=false;
 void StartForestAudio();void Sound(const FName Name,float Volume=1.f,float Pitch=1.f);void Footstep(bool Landing=false);void UpdateFootsteps(float D);void SetAudioPaused(bool Value);
 int32 Ammo=8;float ReloadTime=0,InspectTime=0,Kick=0,Cooldown=0,Sensitivity=1;
 bool Aiming=false,Running=false,WeaponShown=true,Help=false;
 void Forward(float V);void Right(float V);void Yaw(float V);void Pitch(float V);void Fire();void Aim();void UnAim();void Reload();void Inspect();void ToggleWeapon();void ToggleHelp();void Escape();void Sprint();void StopSprint();void CrouchToggle();void Capture();
};
UCLASS()
class AForestMode:public AGameModeBase {
 GENERATED_BODY()
public:
 AForestMode();void BeginPlay() override;void Tick(float D) override;
 bool Paused=false,QuitConfirmation=false,QA=false,Preview=false;int32 Trees=0,Plants=0,Step=0,Failures=0,Frames=0;double Elapsed=0,Sum=0,Worst=0;FVector Previous;
 static float TrailY(float X);static float Height(float X,float Y);
 AForestPlayer* Player() const;void BuildForest();void PauseForest(bool Value);void ResetTrail();void Action(int32 Row);void Check(bool C,const TCHAR* N);void QATick(float D);void Shot(const TCHAR* Name);
};
UCLASS()
class AForestHUD:public AHUD {
 GENERATED_BODY()
public:
 double FPSStart=0;int32 FPSFrames=0;float CurrentFPS=0;
 FName Pressed;void DrawHUD() override;void NotifyHitBoxClick(FName Name) override;void NotifyHitBoxRelease(FName Name) override;
};
