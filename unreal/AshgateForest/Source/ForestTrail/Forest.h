#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "Forest.generated.h"
class UCameraComponent;class UStaticMeshComponent;class USceneComponent;class USoundBase;
UCLASS()
class AForestPlayer:public ACharacter {
 GENERATED_BODY()
public:
 AForestPlayer();void BeginPlay() override;void Tick(float D) override;void SetupPlayerInputComponent(UInputComponent* I) override;
 UPROPERTY() TObjectPtr<UCameraComponent> Camera;
 UPROPERTY() TObjectPtr<USceneComponent> Weapon;
 UPROPERTY() TObjectPtr<UStaticMeshComponent> Slide;
 UPROPERTY() TObjectPtr<UStaticMeshComponent> Magazine;
 UPROPERTY() TObjectPtr<USceneComponent> LeftHand;
 UPROPERTY() TObjectPtr<USoundBase> ShotSound;
 UPROPERTY() TObjectPtr<USoundBase> ReloadSound;
 int32 Ammo=7;float ReloadTime=0,InspectTime=0,Kick=0,Cooldown=0,Sensitivity=1;
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
 FName Pressed;void DrawHUD() override;void NotifyHitBoxClick(FName Name) override;void NotifyHitBoxRelease(FName Name) override;
};
