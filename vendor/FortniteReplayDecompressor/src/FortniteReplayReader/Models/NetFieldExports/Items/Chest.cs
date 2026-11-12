using Unreal.Core.Attributes;
using Unreal.Core.Models;
using Unreal.Core.Models.Enums;
using Unreal.Core.Contracts;

namespace FortniteReplayReader.Models.NetFieldExports.Items;

[NetFieldExportGroup("/Game/Building/ActorBlueprints/Containers/Tiered_Chest_Athena.Tiered_Chest_Athena_C", minimalParseMode: ParseMode.Minimal)]
public class Chest : BaseContainer
{
    [NetFieldExport("bDestroyOnPlayerBuildingPlacement", RepLayoutCmdType.PropertyBool)]
    public bool bDestroyOnPlayerBuildingPlacement { get; set; }

    [NetFieldExport("ResourceType", RepLayoutCmdType.Enum)]
    public int ResourceType { get; set; }

    [NetFieldExport("ProxyGameplayCueDamagePhysicalMagnitude", RepLayoutCmdType.Ignore)]
    public DebuggingObject ProxyGameplayCueDamagePhysicalMagnitude { get; set; }

    [NetFieldExport("EffectContext", RepLayoutCmdType.Ignore)]
    public DebuggingObject EffectContext { get; set; }
}

[NetFieldExportGroup("/Game/Building/ActorBlueprints/Containers/Creative_Tiered_Chest.Creative_Tiered_Chest_C", minimalParseMode: ParseMode.Minimal)]
public class CreativeChest : Chest
{
    [NetFieldExport("SpawnItems", RepLayoutCmdType.Property)]
    public DebuggingObject SpawnItems { get; set; }

    [NetFieldExport("PrimaryAssetName", RepLayoutCmdType.Property)]
    public DebuggingObject PrimaryAssetName { get; set; }

    [NetFieldExport("Quantity", RepLayoutCmdType.Property)]
    public DebuggingObject Quantity { get; set; }
}

[NetFieldExportGroup("/Game/Building/ActorBlueprints/Containers/Tiered_Chest_Athena_FactionChest_NoLocks.Tiered_Chest_Athena_FactionChest_NoLocks_C", minimalParseMode: ParseMode.Minimal)]
public class FactionChest : BaseContainer
{
    [NetFieldExport("bDestroyOnPlayerBuildingPlacement", RepLayoutCmdType.PropertyBool)]
    public bool? bDestroyOnPlayerBuildingPlacement { get; set; }

    [NetFieldExport("T_Faction", RepLayoutCmdType.Enum)]
    public int? Faction { get; set; }
}

// Ajout fortnite-stats : coffres spéciaux de la saison (sinon ni vus ni comptés)
[NetFieldExportGroup("/RelicChest/Gameplay/B_TieredChest_Relics.B_TieredChest_Relics_C", minimalParseMode: ParseMode.Minimal)]
public class RelicChest : BaseContainer { }
[NetFieldExportGroup("/Game/Building/ActorBlueprints/Containers/AlwaysSpawn_RareChest.AlwaysSpawn_RareChest_C", minimalParseMode: ParseMode.Minimal)]
public class RareChest : BaseContainer { }
[NetFieldExportGroup("/Game/Athena/Items/ForagedItems/BuriedChest/B_Athena_BuriedChest_Chest.B_Athena_BuriedChest_Chest_C", minimalParseMode: ParseMode.Minimal)]
public class BuriedChest : BaseContainer { }
[NetFieldExportGroup("/ExtractionPointGameplay/Gameplay/BGA_ExtractionPointGameplay_Chest.BGA_ExtractionPointGameplay_Chest_C", minimalParseMode: ParseMode.Minimal)]
public class ExtractionChest : BaseContainer { }
[NetFieldExportGroup("/SpritePosters/Blueprints/Items/Booty/B_SpritePosters_Booty_Chest.B_SpritePosters_Booty_Chest_C", minimalParseMode: ParseMode.Minimal)]
public class BootyChest : BaseContainer { }
// Variantes de la saison (liste reprise de oneboyler/fortnite-chest-counter)
[NetFieldExportGroup("/Game/Building/ActorBlueprints/Containers/AlwaysSpawn_NormalChest.AlwaysSpawn_NormalChest_C", minimalParseMode: ParseMode.Minimal)]
public class AlwaysSpawnChest : BaseContainer { }
[NetFieldExportGroup("/SpritePosters/Gameplay/RelicChests/B_Delilah_TieredChest_Relics_Variant1.B_Delilah_TieredChest_Relics_Variant1_C", minimalParseMode: ParseMode.Minimal)]
public class RelicChestV1 : BaseContainer { }
[NetFieldExportGroup("/SpritePosters/Gameplay/RelicChests/B_Delilah_TieredChest_Relics_Variant2.B_Delilah_TieredChest_Relics_Variant2_C", minimalParseMode: ParseMode.Minimal)]
public class RelicChestV2 : BaseContainer { }
[NetFieldExportGroup("/ExtractionRelicFinder/Gameplay/Chests/B_Athena_BuriedChest_RelicFinder.B_Athena_BuriedChest_RelicFinder_C", minimalParseMode: ParseMode.Minimal)]
public class BuriedChestRelicFinder : BaseContainer { }
[NetFieldExportGroup("/SpritePosters/Blueprints/Items/Booty/B_SpritePosters_Booty_Chest_Variant1.B_SpritePosters_Booty_Chest_Variant1_C", minimalParseMode: ParseMode.Minimal)]
public class BootyChestV1 : BaseContainer { }
[NetFieldExportGroup("/SpritePosters/Blueprints/Items/Booty/B_SpritePosters_Booty_Chest_Variant2.B_SpritePosters_Booty_Chest_Variant2_C", minimalParseMode: ParseMode.Minimal)]
public class BootyChestV2 : BaseContainer { }

// Ajout fortnite-stats : objets "donnés" par un acteur (récompenses de coffre au trésor ?)
public class GrantedItemEntry
{
    [NetFieldExport("ItemDefinition", RepLayoutCmdType.Property)]
    public ItemDefinition ItemDefinition { get; set; }

    [NetFieldExport("Amount", RepLayoutCmdType.PropertyInt)]
    public int? Amount { get; set; }
}

[NetFieldExportGroup("/Script/FortniteGame.GrantedItemProviderComponent", minimalParseMode: ParseMode.Minimal)]
public class GrantedItemProvider : INetFieldExportGroup
{
    [NetFieldExport("ReplicatedItemsToGrant", RepLayoutCmdType.DynamicArray)]
    public GrantedItemEntry[] ReplicatedItemsToGrant { get; set; }

    [NetFieldExport("ItemDefinition", RepLayoutCmdType.Property)]
    public ItemDefinition ItemDefinition { get; set; }

    [NetFieldExport("Amount", RepLayoutCmdType.PropertyInt)]
    public int? Amount { get; set; }
}

// Ajout fortnite-stats : gizmos (armes "utilitaires" tenues par un joueur ; Instigator = son pawn)
public abstract class GizmoWeapon : FortniteReplayReader.Models.NetFieldExports.Weapons.BaseWeapon { }
[NetFieldExportGroup("/ExtractionRelicExtractor/Gameplay/B_RelicExtractor.B_RelicExtractor_C", minimalParseMode: ParseMode.Minimal)]
public class GizmoPortableExtractor : GizmoWeapon { }
[NetFieldExportGroup("/ExtractionRelicExtractor/Gameplay/B_RelicExtractor_Reload.B_RelicExtractor_Reload_C", minimalParseMode: ParseMode.Minimal)]
public class GizmoPortableExtractorReload : GizmoWeapon { }
[NetFieldExportGroup("/FlameCeleb/Gameplay/B_FlameCeleb_BaseWeapon.B_FlameCeleb_BaseWeapon_C", minimalParseMode: ParseMode.Minimal)]
public class GizmoGoldenFirework : GizmoWeapon { }
[NetFieldExportGroup("/SmugglerExtractionKey_Gizmo/Gameplay/B_SmugglerExtractionKey.B_SmugglerExtractionKey_C", minimalParseMode: ParseMode.Minimal)]
public class GizmoExtractionAccelerator : GizmoWeapon { }
[NetFieldExportGroup("/ExtractionRelicFinder/Gameplay/B_LuckyLocator.B_LuckyLocator_C", minimalParseMode: ParseMode.Minimal)]
public class GizmoLuckyLocator : GizmoWeapon { }
[NetFieldExportGroup("/ExtractionRelicFinder/Gameplay/B_RelicFinder.B_RelicFinder_C", minimalParseMode: ParseMode.Minimal)]
public class GizmoSpriteLocator : GizmoWeapon { }
