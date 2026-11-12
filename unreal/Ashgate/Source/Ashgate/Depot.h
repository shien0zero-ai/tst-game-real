#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/HUD.h"
#include "GameFramework/SaveGame.h"
#include "Depot.generated.h"

class UCameraComponent;
class UStaticMeshComponent;
class USceneComponent;
class USoundBase;
class ADepotGuard;

UCLASS()
class UDepotProfile : public USaveGame {
    GENERATED_BODY()
public:
    UPROPERTY() int32 Version = 1;
    UPROPERTY() int32 Credits = 1800;
    UPROPERTY() int32 Guns = 2;
    UPROPERTY() int32 Rounds = 84;
    UPROPERTY() int32 Kits = 4;
    UPROPERTY() TMap<FString,int32> Goods;
    UPROPERTY() bool ActiveRaid = false;
    UPROPERTY() float Sensitivity = 1.f;
    UPROPERTY() int32 Quality = 2;
};

UCLASS()
class ADepotPlayer : public ACharacter {
    GENERATED_BODY()
public:
    ADepotPlayer();
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;
    UPROPERTY() TObjectPtr<UCameraComponent> Camera;
    UPROPERTY() TObjectPtr<USceneComponent> Weapon;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Slide;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> Magazine;
    UPROPERTY() TObjectPtr<USceneComponent> LeftHand;
    UPROPERTY() TObjectPtr<USoundBase> ShotSound;
    UPROPERTY() TObjectPtr<USoundBase> ReloadSound;
    UPROPERTY() TObjectPtr<USoundBase> EmptySound;
    int32 Ammo = 7, Reserve = 28, Kits = 1;
    float Health = 100, Stamina = 100, HealTime = 0, ReloadTime = 0, InspectTime = 0, Cooldown = 0, Kick = 0;
    bool Aiming = false, Running = false, Bleeding = false;
    void Fire(); void Reload(); void Inspect(); void Aim(); void UnAim();
    void Heal(); void Hurt(float Damage); void Interact(); void Bag(); void Escape();
    void ResetLoadout(int32 TotalRounds, int32 Meds);
    void Forward(float Value); void Right(float Value); void Yaw(float Value); void Pitch(float Value);
    void Sprint(); void StopSprint(); void JumpPressed(); void PracticeReset();
    void CaptureProbe();
    bool CanAct() const;
};

UCLASS()
class ADepotGuard : public ACharacter {
    GENERATED_BODY()
public:
    ADepotGuard();
    UPROPERTY() TObjectPtr<USceneComponent> Sidearm;
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    FVector Home, Goal;
    float Health = 80, ShotTimer = 1, Awareness = 0, Phase = 0;
    bool Dead = false;
    void Hit(float Damage);
};

UCLASS()
class ADepotGameMode : public AGameModeBase {
    GENERATED_BODY()
public:
    ADepotGameMode();
    virtual void BeginPlay() override;
    virtual void Tick(float Delta) override;
    UPROPERTY() TObjectPtr<UDepotProfile> Profile;
    UPROPERTY() TArray<TObjectPtr<ADepotGuard>> Guards;
    UPROPERTY() TArray<TObjectPtr<AActor>> Cases;
    TArray<FString> BagItems;
    TArray<bool> Searched;
    FString Phase = TEXT("base"), Message, Focus, Slot;
    bool BagOpen = false, Paused = false, Practice = false, SaveHealthy = true, QA = false;
    float RaidTime = 600, ExtractTime = 0, MessageTime = 0;
    FVector Extraction = FVector(4050,3550,0);
    void BuildDepot(); void StartRaid(bool IsPractice=false); void FinishRaid(bool Success, const FString& Reason);
    void Save(); void Notice(const FString& Text); void Use(); void MenuAction(int32 Row); void Pause(bool Value);
    int32 FindCase() const; int32 ValueOf(const FString& Item) const;
    ADepotPlayer* Player() const;
    void QATick(float Delta);
    void QATestField();
    int32 QAStep = 0, QAFailures = 0, QASamples = 0;
    double QAElapsed = 0, QASum = 0, QAMax = 0;
    FVector QAPosition;
    void Check(bool Condition, const TCHAR* Name);
};

UCLASS()
class ADepotHUD : public AHUD {
    GENERATED_BODY()
public:
    virtual void DrawHUD() override;
    void Click(float X, float Y);
    float Scale = 1;
    void Text(const FString& Value, float X, float Y, float Size=1, FLinearColor Color=FLinearColor::White);
    void Panel(float X, float Y, float W, float H, FLinearColor Color);
};
