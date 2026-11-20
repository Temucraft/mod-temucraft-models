# mod-temucraft-models

Looks that were already in the Temucraft client but that nothing used, made usable:

- **1,096 showcase creatures** (`creature_template` from 1210000): 936 creature models that had no model row, a few that
  had a model row but no display, and new skins for creatures the client already shows. Each has its own model row
  (CreatureModelData from 46000), display (CreatureDisplayInfo from 1210000) and size row (`creature_model_info`). They
  are friendly, can't be attacked, level 1, and are not spawned: `.npc add <entry>` to place one. The subname says which
  model it uses.
- **1,865 fully cosmetic items** (`item_template` from 1210000): weapons, shields, helms, shoulders, belts and armour
  pieces made from the free item models and armour textures, each with its own ItemDisplayInfo row (from 1210000).
  Item level 1, no stats, no armour, bind on pickup, no durability: for transmog and for looks.
- **2,221 NPC outfits as cosmetic item sets**: what NPCs wear (helm, shoulders, shirt, chest, belt, legs, boots,
  bracers, gloves, tabard, cloak) and their weapons, as fully cosmetic items (`item_template` from 1220000), grouped into a
  real item set each (ItemSet from 4000: the tooltip shows "Stormwind City Guard's Outfit" and its pieces, with no
  bonuses), plus an outfit box that gives the whole set. First the city guards (Stormwind, Ironforge, Darnassus, Exodar,
  Orgrimmar, Kor'kron, Thunder Bluff), then every elite, rare and boss that wears at least four armour pieces. Outfits
  that are exactly the same are made once, named after the first NPC found (bosses first); a second different outfit of
  the same NPC gets "II". The pieces use the NPCs' own item looks; 5,100 of those looks had no icon, so they get a copy
  with the slot's plain icon (ItemDisplayInfo from 1220000). Undercity and Silvermoon guards have no separate item looks.
Names come from the item or creature that uses the same model in the current game, so they can be looked up on Wowhead.

## Install

1. Put the folder in `modules/`, re-run CMake and build (the module is SQL only). The worldserver applies
   `data/sql/db-world/base/temucraft_models.sql` on its next start. The file deletes its own ranges first, so it can run again.
2. **The client needs the same rows.** `client/DBFilesClient/` holds CreatureModelData, CreatureDisplayInfo,
   ItemDisplayInfo, Item.dbc and ItemSet.dbc: the client's current tables (patch-T) with these rows added. Put them into the client
   patch that carries those tables (patch-T, or merge them into patch-5), and copy them to the server's `dbc` folder too.
   Without them the client shows nothing, or a question mark, for these creatures and items.

## Ids

| What | Range |
|---|---|
| CreatureModelData | 46000-48999 (936 used) |
| CreatureDisplayInfo, `creature_model_info` | 1210000-1219999 |
| `creature_template`, `creature_template_model` | 1210000-1219999 |
| ItemDisplayInfo | 1210000-1219999 |
| `item_template`, Item.dbc (free models) | 1210000-1219999 |
| `item_template`, Item.dbc, `item_loot_template` (outfits) | 1220000-1259999 |
| ItemDisplayInfo (outfit pieces given an icon) | 1220000-1259999 |
| ItemSet | 4000-6999 |

The ranges are SQL variables at the top of the file.

## Known limits

- Only models whose file our client has in the 3.3.5 format, and whose current-game look could be rebuilt from files we
  have, are included (1,438 item looks were left out because a texture or model of that look is missing).
- Retail icons that our client doesn't have are replaced by a plain icon for the slot.
- Belt buckle models: the 3.3.5 client draws only the belt's textures, not the buckle.
- Nothing here has been looked at in game yet: some converted models may still look wrong.

## Rebuilding

`tools/catalog.py` lists the unused files (it reads the MPQ listings and the client tables) and `tools/gen_models.py`
writes the SQL and the client tables. They need the MPQ listings, the client's DBCs from patch-T, the community
listfile and the current-game tables (CreatureModelData, CreatureDisplayInfo, Creature, ItemDisplayInfo,
ItemAppearance, ItemModifiedAppearance, Item, ItemSparse, ModelFileData, TextureFileData,
ItemDisplayInfoMaterialRes as CSV). The guard list is `GUARDS` in `gen_models.py`; other NPCs are every creature with rank 1 or higher.
