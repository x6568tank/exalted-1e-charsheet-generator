# 1E artifact backlog — per-book authoring checklists (2026-08-08)

Pre-computed authoring queues from the **"When Autochthon Dreams"** index (see `docs/status/artifact-backlog.md` for the discovery record and the parse). Every 1E artifact is listed under each source book it references, with the guide's rating and book page, sorted by page. **Values still come from the real pages** — this is book+page discovery only, and the never-author-from-memory rule applies. Syncing a book's missing pages unblocks its whole share at once.

**Build** column = whether the build already holds a matching name: `rated` = an equipment row carrying `artifact_rating` (a rated artifact in the weapons/armour catalogues), `gear` = a mundane equipment row exists, `cat` = a standalone rated-artifact catalogue entry in `data/artifacts.json` (added 2026-08-08 — non-gear artifacts like Shield Bracer live only there), `—` = not in the build. Names were matched case/punctuation-insensitively; `Lightning Torment Hatchet` matches the build's two `(Thrown)`/`(Melee)` rows. `blocked` = flagged non-authorable — the guide's entry has no matching text in the book (see the `cb_e` note for the one case).

The legend and on-disk flags below were **verified against `images/` this session (2026-08-08)** and correct `artifact-backlog.md`, whose original draft mislabelled five codes (marked ⚠ below — the five `ab_*` codes are the Dragon-Blooded **Aspect Books**, not "Abyssal" anything; `salt` is **Blood and Salt**, not "Salt & Smoke"; `coin` is **Manacle and Coin**, not "Coin of the Realm") and overstated what is on disk.

## The books, with on-disk status

| Code | Book | Entries | Pages | On disk? |
|---|---|---|---|---|
| bone | Bone & Ebony | 74 | 58-79, 104, 113-114 | NO |
| outc | Outcastes | 27 | 50-54, 58-59, 62-64, 92, 121-122 | NO |
| fair | Fair Folk | 27 | 205-211; 279-283 (MF ch.) | 205-211 NO; 279-283 DONE (10 in data/artifacts.json) |
| core | Exalted core rules | 24 | 336-338, 340-341, 343-345 | PARTIAL — 341,343,344,345 (+ 342,327-331 stat tables) |
| ruin | Ruins of Rathess | 18 | 80-84, 86-88, 91, 194 | NO |
| auto | The Autochthonians | 17 | 182-190 | NO |
| abys | Abyssals | 16 | 254-261 | NO (only Traits 130-153 on disk) |
| botc | Book of Three Circles | 14 | 24-27, 92-96 | NO |
| play | Player's Guide | 14 | 192-195, 211 | NO |
| ab_a | Aspect Book: Air ⚠ | 13 | 75-78, 81 | NO |
| cb_d | Caste Book: Dawn | 11 | 78-81 | YES — all 11 |
| time | Time of Tumult | 11 | 15, 23, 49, 94-95 | NO |
| cb_t | Caste Book: Twilight | 12 | 79-81 | YES — pp.79-81 VLM-transcribed 2026-08-08 (79-81 on disk) |
| salt | Blood and Salt ⚠ | 11 | 89, 119-124 | NO |
| cb_e | Caste Book: Eclipse | 9 | 79-81 | YES — pp.79-81 VLM-transcribed 2026-08-08 (79-81 on disk) |
| cb_n | Caste Book: Night | 8 | 79-81 | YES — all 8 |
| ab_e | Aspect Book: Earth ⚠ | 6 | 79-81 | NO |
| ab_w | Aspect Book: Wood ⚠ | 6 | 79-81 | NO |
| comp | Storyteller's Companion | 6 | 77-80 | NO (only CH3 spirit pages on disk) |
| cb_z | Caste Book: Zenith | 5 | 80-81 | YES — all 5 |
| seas | Savage Seas | 4 | 123-124, 126-127 | NO |
| ab_f | Aspect Book: Fire ⚠ | 4 | 79-81 | NO |
| ab_v | Aspect Book: Water ⚠ | 4 | 80-81 | NO |
| cult | Cult of the Illuminated | 5 | 69-70 | NO (only the p.89+ chargen paste on disk) |
| halt | Kingdom of Halta | 5 | 93-95 | NO |
| svnt | Savant & Sorcerer | 5 | 40-43 | NO |
| side | Sidereals | 3 | 24, 39 | NO (only 96-125, 128-201, Storytelling) |
| coin | Manacle and Coin ⚠ | 1 | 31 | NO |

**Authorable NOW, no sync needed: 40 entries** — Caste Book Dawn (11), Caste Book Night (8), Caste Book Zenith (5), and the core-book subset (16, via the Arms & Armor table crops). **2026-08-08: the 12 genuinely-new remainder were addressed** — ten became standalone catalogue entries in `data/artifacts.json` (`cat` below; the eight non-gear items plus the Hooked Daiklaves of Dual Prowess, which also got a rated weapon row), the **Direlance** got a rated weapon row from the p.342 Daiklave Table but its catalogue entry is BLOCKED (the p.341 description page is not on disk — the crop is the Materials section), and the **Slayer Khatar** is fully BLOCKED (neither description nor stat block on disk; p.344's crop is the Lightning Torment Hatchet). See `docs/status/rated-artifacts.md` → *The 2026-08-08 castebook batch*. The other 28 already have rated-equipment rows (the Solar-castebook gear work and a few Aspect-Book rows — e.g. Forge-Hand Gauntlets) — see the `Build` column. **Already done:** the ten Fair Folk 279-283 entries (= the Mountain Folk Technology artifacts in `data/artifacts.json`). Everything else needs the human to sync pages. The earlier ~90 estimate was wrong — Abyssal Traits 254-261, the Sidereals and Illuminated artifact pages, and Caste Books Twilight/Eclipse are **NOT** on disk.

## The queues, by book

### `bone` — Bone & Ebony (74)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Blood Apples | • | 58 | — |
| Bloody Ice Comb | • | 58 | — |
| Collar of the Bestial Shade | • | 58 | — |
| Drum of the Living Heart | • | 59 | — |
| Forms of Harmony | • | 59 | — |
| Grapes of Torment | • | 59 | — |
| Ivory Butterfly | • | 59 | — |
| Jade Harmony Needles | • | 60 | — |
| Labyrinth Doorknocker | • | 60 | — |
| Mirror of Life | • | 60 | — |
| Pillow of Grass | • | 60 | — |
| Robe of Life | • | 61 | — |
| Scroll of Unending Stories | • | 61 | — |
| Stallion-Thrashing Whip | • | 61 | — |
| Steel Pen of Refinement | • | 61 | — |
| Stone of Ten Thousand Tears | • | 62 | — |
| Storm-Running Boots | • | 62 | — |
| Storm-Warding Parasol | • | 62 | — |
| Thirst-Quenching Pitcher | • | 62 | — |
| Bag of Harvested Plagues | •• | 63 | — |
| Bone Bridge | •• | 63 | — |
| The Tongue-Binder | • | 63 | — |
| Whip of the Dead | • | 63 | — |
| Bone Harpoon | •• | 64 | — |
| Bracelets of Passionate Artistry | •• | 64 | — |
| Candelabrum of Remembered Kin | •• | 64 | — |
| Chair of Guilty Sorrows | •• | 65 | — |
| Cloak of Vermin | •• | 65 | — |
| Essence Dice | •• | 65 | — |
| Fingerbone Bracelet | •• | 65 | — |
| Hairpin Blade | •• | 66 | — |
| Hilt of the Bloody Sword | •• | 66 | — |
| Inkbrush of the Heart’s Desire | •• | 66 | — |
| Onyx Soul Window | •• | 67 | — |
| Patch Hide Armor | •• | 67 | — |
| Ring of Flies | •• | 67 | — |
| The Loom of Cobwebs | •• | 67 | — |
| Sacrificial Gem | •• | 68 | — |
| Shadow Gloves | •• | 68 | — |
| Shadow Peacock Earring | •• | 68 | — |
| The Speaking Dagger | •• | 69 | — |
| Whispering Fan | •• | 69 | — |
| Worm-Ridden Veil | •• | 69 | — |
| Bath That Warms | ••• | 70 | — |
| Bell of the Endless Caravan | ••• | 70 | — |
| Boat of Bones | ••• | 70 | — |
| Bow of Screaming Doom | ••• | 70 | — |
| Chart of the Final Lands | ••• | 71 | — |
| Eyes of the Pyre Flame | ••• | 72 | — |
| The Codex of the Damned | ••• | 72 | — |
| The Crusher of Souls | ••• | 72 | — |
| Fire-Belly Centipede | ••• | 73 | — |
| Girdle of Skulls | ••• | 73 | — |
| Hammer of the Damned | ••• | 73 | — |
| Hand Snare Chains | ••• | 73 | — |
| Mirror That Looks Upon Its Twin | ••• | 74 | — |
| Night Mother Doll | ••• | 74 | — |
| Pale Bees of the Ghostly Hive | ••• | 74 | — |
| Phantom Mantle | ••• | 75 | — |
| Razor Teeth | ••• | 75 | — |
| Rosary That Feeds on Souls | ••• | 75 | — |
| Scourge of Thorns | ••• | 75 | — |
| Shadow-Casting Gem | ••• | 76 | — |
| Stomach-Weighting Powder | ••• | 77 | — |
| Taming Muzzle | ••• | 77 | — |
| Thieving Harness of Servitude | ••• | 77 | — |
| Urn That Voids Darkness | ••• | 78 | — |
| Keystone of the Stair Inescapable | •••• | 79 | — |
| The White Snakes That Hunger | ••• | 79 | — |
| Bonestrider | ••••• | 104 | — |
| The Insidious Ebon Xoanon | n/A | 104 | — |
| Manifestation Engine | •••• | 113 | — |
| Soulsteel Mesh Swathing | ••••• | 114 | — |
| Soulsteel Net | •••• | 114 | — |

### `outc` — Outcastes (27)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Ashigaru Battle Armor | •• | 50 | — |
| Reaper Daiklave | •• | 51 | — |
| Shock Pike | •• | 51 | — |
| Warstrider Implosion Bow | •• | 51 | — |
| Elemental Lens | ••• | 52 | — |
| Essence Cannon | •• | 52 | — |
| Fire Lance | ••• | 53 | — |
| Gunzosha Commando Armor | ••• | 53 | — |
| Armor of the Immaculate Dragons | •••• | 54 | — |
| Infinite Weapon | ••• | 54 | — |
| Haze Shield | •••• | 58 | — |
| Crimson Armor of the Unseen Assassin | ••••• | 59 | — |
| Implosion Bow, Medium | •••• | 59 | — |
| Warstrider Fire Lance | •••• | 59 | — |
| Warstrider Shock Ram | •••• | 59 | — |
| Chariot of the Infinite Heavens | •••• | 62 | — |
| Manta-class Transport | ••••• | 63 | — |
| Kireeki-class Assault Skyreme | n/A | 64 | — |
| Compass of the Immanent Strife | •• | 92 | — |
| Freshwater Pearls | • | 92 | — |
| Helm of Heart’s Desire | ••••• | 92 | — |
| Wave Stepping Boots | •• | 92 | — |
| Perfected Flame | ••• | 121 | — |
| Six-and-Finger Staff | • | 121 | — |
| Veil of the Anointed | •• | 121 | — |
| Dominca’s Mantle | ••••• | 122 | — |
| Walking Stone | ••• | 122 | — |

### `fair` — Fair Folk (27)

**279-283** = the Mountain Folk Technology chapter (already the ten entries in `data/artifacts.json` — those rows are DONE). **205-211** is the Fair Folk splatbook; decision 0010 bars the *splat*, and the human must decide on the *artifacts* before authoring any of them (see `artifact-backlog.md`).

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Oneiromancy: Waking Circle Spell | • | 205 | — |
| Oneiromancy: Desire Circle Spell | ••• | 206 | — |
| Oneiromancy: Dreaming Circle Spell | •• | 206 | — |
| Artifact Waypoint Complex | ••• | 207 | — |
| Hundred Color Shaping Lens | •• | 207 | — |
| Oneiromancy: Samadhi Circle Spell | •••• | 207 | — |
| Oneiromancy: Shinma Circle Spell | ••••• | 207 | — |
| Resonant Chorus Bow | • | 207 | — |
| Adjuration: Sahmara Oath | • | 208 | — |
| Adjuration: Sthiti Oath | •• | 208 | — |
| Adjuration: Anugraha Oath | ••• | 209 | — |
| Adjuration: Srishti Oath | ••••• | 209 | — |
| Adjuration: Tirobhava Oath | •••• | 209 | — |
| Behemoth: Daikaiju | ••• | 210 | — |
| Behemoth: Fey Beast | • | 210 | — |
| Behemoth: Deep Wyld Horror | •••• | 211 | — |
| Ishiika | n/A | 211 | — |
| Essence-Scrying Visor | • | 279 | cat |
| Hammerfist Bracer | • | 279 | cat |
| Mask of Pure Breath | • | 279 | cat |
| Echo Jewel | • | 280 | cat |
| Skirmish Pike | • | 280 | rated |
| Dragon Sigh Wand | •• | 281 | rated |
| Talisman of Suspended Evocation | • | 281 | cat |
| Essence Pulse Grenade | •• | 282 | rated |
| Shieldstone Gauntlet | •• | 282 | cat |
| Myrmidon Carapace | ••• | 283 | rated |

### `core` — Exalted core rules (24)

On-disk page → crop (all in `images/Image Archive 1/Arms & Armor/`):

- **p.341** → `Artifact Materials Exalted.pdf p341.png`
- **p.343** → `Powerbow Table Exalted.pdf p343.png`
- **p.344** → `Lightning Torment Hatchent Exalted.pdf p344.png`
- **p.345** → `Artifact Armor Material Rules Exalted.pdf p345.png`
- **p.342** → `Daiklave Table Exalted.pdf p342.png` (not a guide page, but the stat table for the p.341 daiklaves); the general weapons tables p327-331 are also on disk.

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Charm against disease | • | 336 | — |
| Dragon Tear Tiara | •• | 337 | — |
| Good Luck Charm | • | 337 | — |
| Hearthstone Amulet | • | 337 | — |
| Walkaway | • | 337 | — |
| Warding charms | • | 337 | — |
| Hearthstone Bracers | •• | 338 | — |
| Daiklave | •• | 340 | rated |
| Direlance | •• | 341 | rated |
| Goremaul | • | 341 | rated |
| Grand Daiklave | ••• | 341 | rated |
| Grimcleaver | •• | 341 | rated |
| Reaver Daiklave | •• | 341 | rated |
| Serpent Sting Staff | •• | 341 | rated |
| Smashfist | • | 341 | rated |
| Long Powerbow | ••• | 343 | rated |
| Short Powerbow | •• | 343 | rated |
| Lightning Torment Hatchet | ••••• | 344 | rated |
| Slayer Khatar | •• | 344 | — |
| Articulated Plate | •••• | 345 | rated |
| Breastplate | • | 345 | rated |
| Reinforced Breastplate | ••• | 345 | rated |
| Reinforced Buff Jacket | •• | 345 | rated |
| Superheavy Plate | ••••• | 345 | rated |

### `ruin` — Ruins of Rathess (18)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Boot Grafts | • | 80 | — |
| Breather Plant | • | 80 | — |
| Green Eyes | • | 80 | — |
| Green Iron Dust | • | 81 | — |
| Knife Spores | • | 81 | — |
| Healing Orchid | •• | 82 | — |
| Vine Klave | • | 82 | — |
| Mimic Skin | •• | 83 | — |
| Sun crystal | • | 84 | — |
| Crystal of Protection | ••• | 86 | — |
| Ring of Disguise | ••• | 86 | — |
| Ring of Images | •• | 86 | — |
| Lizard Tail Regrowth Sphere | •••• | 87 | — |
| Warbird | •••• | 88 | — |
| Enchiridion of All Knowledge | •• | 91 | — |
| Glory to the Ghoul King | • | 91 | — |
| Shock Gauntlet | ••• | 194 | — |
| Thorn Thrower | ••• | 194 | — |

### `auto` — The Autochthonians (17)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Arc Protector | • | 182 | — |
| Autolabe | • | 182 | — |
| Essence Capacitor | • | 183 | — |
| Essence Capacitor exab.215, | ••• | 183 | — |
| Flaw Scanner | • | 183 | — |
| Light Amplification Visor | • | 183 | — |
| Light Sphere | • | 184 | — |
| Omnimodal Wardrobe Unit | • | 184 | — |
| Courier Drone | •• | 185 | — |
| Nutrient Recycling Engine | • | 185 | — |
| Respirator Module | • | 185 | — |
| Soulgem | •• | 186 | — |
| Industrial Exoskeleton | ••• | 187 | — |
| Assault Crossbow | •• | 188 | rated |
| Fibre-Weave Bodysuit | • | 189 | — |
| Gyroscopic Chakram | ••• | 189 | — |
| Beam-Klave | •••• | 190 | — |

### `abys` — Abyssals (16)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Soulfire Crystal | • | 254 | — |
| Essence Containing Gem | • | 255 | — |
| Chime of Perfect Summoning | • | 256 | — |
| Vessel of the Pyre | • | 256 | — |
| Grave-Prison Chains | •• | 257 | — |
| Morning Star Guide | •• | 257 | — |
| Soulfire Mask | •• | 257 | — |
| Demon-Embracing Robes | ••• | 258 | — |
| Ghost-Strengthening Links | ••• | 258 | — |
| Visage-Distorting Mask | •• | 258 | — |
| Repeating Maggot-Caster | ••• | 259 | — |
| Tongue of 11 Demon Howl | ••• | 259 | — |
| Hovering Iron Spirit | •••• | 260 | — |
| Virtue-Enhancing Flask | ••• | 260 | — |
| Shroud of the Unquiet Dead | •••• | 261 | — |
| Whip of Devouring Serpents | ••••• | 261 | — |

### `botc` — Book of Three Circles (14)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Anastacia’s Chains and Catches | •••• | 24 | — |
| The Crucible of Tarim | ••••• | 24 | — |
| Mantle of Brigid | n/A | 25 | — |
| Spirit Ring | •••• | 26 | — |
| The Sword of Ice | n/A | 27 | — |
| Horn of the Ways | •• | 92 | — |
| Thunderbolt Shield | •• | 93 | — |
| Wedding Bands | • | 93 | — |
| Blood Seed | ••• | 94 | — |
| Dark Rider | ••• | 94 | — |
| Traveller’s Staff | •• | 94 | — |
| The Crimson Bow | •••• | 95 | — |
| Blackened Bones | ••••• | 96 | — |
| The Crown of Thunders | ••••• | 96 | — |

### `play` — Player's Guide (14)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Reading Crystal | • | 192 | — |
| Bracer of Crystal Bolts | •• | 193 | — |
| Fire Claw | •• | 193 | — |
| Swordstick | • | 193 | — |
| Crystal Warclub | ••• | 194 | — |
| Necklace of Solar Charisma | ••• | 194 | — |
| Essence Storing Crystal | •••• | 195 | — |
| Globe of Transport | •••• | 195 | — |
| Obsidian Sheathe | •••• | 195 | — |
| Crushfist | • | 211 | — |
| Daiklave, Short | •• | 211 | — |
| God Kicking Boot | • | 211 | — |
| Grand Goremaul | ••• | 211 | — |
| Infinite Chakram | •• | 211 | — |

### `ab_a` — Aspect Book: Air ⚠ (13)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Dragonfly’s Ranging Eye | • | 75 | — |
| Essence Union Dart | •• | 76 | — |
| Face of Discretion | •• | 76 | — |
| Fivefold Harmonic Regulator | • | 76 | — |
| Lightning Box | •• | 76 | — |
| Mundane Box | • | 76 | — |
| Veil of Privacy | • | 76 | — |
| Windslave Disc | • | 76 | — |
| Sky Mantis Tower | ••• | 77 | — |
| Windslave Terminal | ••• | 77 | — |
| Windwall Terminal | •• | 77 | — |
| Icemind | ••••• | 78 | — |
| Reaver Dragonfly | •••• | 81 | — |

### `cb_d` — Caste Book: Dawn (11)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Chariot of Aerial Conquest | ••••• | 78 | cat |
| Map of Azure Victory | ••• | 78 | cat |
| Razor Claws | • | 78 | rated |
| Shield Bracer | •• | 78 | cat |
| Flame Spear | •••• | 79 | rated |
| Lightning Chain | ••• | 79 | rated |
| Powerbow of Perfect Accuracy | ••• | 80 | rated |
| Spirit Sword | ••• | 80 | rated |
| Arrows of Distant Death | ••• | 81 | cat |
| Chain Shirt | •• | 81 | rated |
| Daiklave of Conquest | ••••• | 81 | rated |

### `time` — Time of Tumult (11)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Orichalcum Lined Cloak | • | 15 | — |
| The Golden Soldiers | • | 15 | — |
| The Hound’s Eyes | •• | 15 | — |
| The Perfect Talon Dagger | •• | 23 | — |
| The Golden Flames | • | 49 | — |
| Everyman Armor | ••• | 94 | — |
| Living Glaive | ••• | 94 | — |
| Panacea Pipe | •••• | 94 | — |
| Riding Boots | ••• | 95 | — |
| Sword of Forgetfulness | ••••• | 95 | — |
| The Unsurpassed Sanxian | •••• | 95 | — |

### `cb_t` — Caste Book: Twilight (12)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Bracer of the Hawk | •• | 79 | cat |
| Cup of Flowing Blood | ••• | 79 | cat |
| Seed of the Immaculate Blood | •• | 79 | cat |
| Whistle of Ghost Summoning | •• | 79 | cat |
| Eye of the Living Earth | ••• | 80 | cat |
| Ghost Seeing Blindfold | ••• | 80 | cat |
| Honey of the Bees of Zarlath | ••• | 80 | cat |
| Mirrors of Illusion Shattering | ••• | 80 | cat |
| Scabbard of the Living Weapon | ••• | 80 | cat |
| Sorcery Capturing Cord | ••• | 81 | cat |
| The Jackal’s Skull | •••• | 81 | cat |
| Veil that Holds Back Time | •••• | 81 | cat |

### `salt` — Blood and Salt ⚠ (11)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Jade Hand | • | 89 | — |
| Automaton Assassin | •• | 119 | — |
| Cord of Winds | • | 119 | — |
| Implosion Bow, Light | •• | 120 | — |
| Steelsilk Sails | •• | 121 | — |
| Storm Sapphire | ••• | 121 | — |
| Ancestor Sash | •••• | 122 | — |
| Masks that Command Animals | ••••• | 123 | — |
| The Seven Lotus Crown | •••• | 123 | — |
| Talisman of the Cult of Dukantha | ••••• | 124 | — |
| The Coral Crown | ••••• | 124 | — |

### `cb_e` — Caste Book: Eclipse (9)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Audient Brush | •• | 79 | blocked |
| Lotus Blossom Cup | • | 79 | cat |
| Players Mask | • | 79 | cat |
| Silver Quill | • | 79 | cat |
| Seven Jewelled Peacock Fans | •• | 80 | cat |
| Silken Armor | ••• | 80 | cat |
| Solar Seal | • | 80 | cat |
| Folding Ship | •••• | 81 | cat |
| Iron Horse | •••• | 81 | cat |

**⚠ Audient Brush is blocked 2026-08-08 — a phantom index row.** Caste Book: Eclipse pp.79-81 were VLM-transcribed this day (VLM + tesseract, plus a full 98-page word-sweep of the Eclipse PDF) and the book contains **no** Audient Brush. The real p.79 artifact list is Lotus Blossom Cup, Player's Mask, Silver Quill. Every "brush" in the book is prose or the Larceny Charms Whirling Brush Method / Flawless Brush Discipline. The "When Autochthon Dreams" index either hallucinated the row or misattributed an artifact from another book — authoring needs a real source. The cb_e authorable count is therefore **8, not 9**.

### `cb_n` — Caste Book: Night (8)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Sling of Deadly Prowess | • | 79 | rated |
| Spider Grippers | •• | 79 | cat |
| Belt of Shadow Walking | ••• | 80 | cat |
| Circlet of Spirits | ••• | 80 | cat |
| Gauntlets of Distant Claws | ••• | 80 | rated |
| Ultimately Useful Tube | ••• | 80 | rated |
| Cloak of Vanishing Escape | •••• | 81 | rated |
| Daiklave, Hooked | •• | 81 | cat |

**⚠ The guide's "Daiklave, Hooked ••" is a checklist mislabel, not an unauthored artifact.** Night p.81's heading is *Hooked Daiklaves of Dual Prowess (Artifact ••••)* — the guide's rating and word order both differ, so the name matcher missed it. The build holds it under its real name: `artifact.castebook-night.hooked-daiklaves-of-dual-prowess` (••••, catalogue) plus the `weapon.melee.hooked_daiklaves_of_dual_prowess` rated row. Covered by the closed 2026-08-08 Hooked Daiklaves rating ruling (heading •••• canonical).

### `ab_e` — Aspect Book: Earth ⚠ (6)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Cache Egg | • | 79 | — |
| Hearthstone Compass | • | 79 | — |
| Perfected Kata Bracers | •••• | 80 | — |
| Skin Mount Amulet | •• | 80 | — |
| Duelling Torcs | ••• | 81 | — |
| Emerald Thurible | ••••• | 81 | — |

### `ab_w` — Aspect Book: Wood ⚠ (6)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Black Widow Razors | ••• | 79 | rated |
| Chalcedony Chamberlain’s Flutes | • | 79 | — |
| Harrowed Daughter’s Paleskin Cowl | •• | 79 | — |
| Saram Saru’s Oracular Hookah | ••• | 80 | — |
| Death at the Root | •••• | 81 | rated |
| Prey Stalking Bow | •••• | 81 | — |

### `comp` — Storyteller's Companion (6)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Ghost Cestus | ••• | 77 | — |
| Sling Bow of Ice | ••• | 78 | — |
| The Golden Viper | ••••• | 78 | — |
| Land Ship | ••••• | 79 | — |
| Singing Staff | •••• | 79 | — |
| Eye of Autochthon | n/A | 80 | — |

### `cb_z` — Caste Book: Zenith (5)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Death Shield Ring | ••• | 80 | cat |
| Heavenly Thunder Leaves | • | 80 | rated |
| Reborn Glacial Rain | ••• | 80 | rated |
| Flying Silver Dream | •••• | 81 | rated |
| Ring of the Deliberative | ••••• | 81 | cat |

### `seas` — Savage Seas (4)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Cargo Preservation Spindles | ••• | 123 | — |
| Armor of Aquatic Puissance | •••• | 124 | — |
| Wavecleaver Daiklave | •• | 126 | — |
| Lightning Ballistae | ••• | 127 | — |

### `ab_f` — Aspect Book: Fire ⚠ (4)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Fire Pearl | • | 79 | — |
| Transcendent Phoenix Pinions | ••• | 79 | — |
| Forge Hand Gauntlets | •••• | 80 | rated |
| Eye of the Fire Dragon | ••••• | 81 | rated |

### `ab_v` — Aspect Book: Water ⚠ (4)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Gauntlets of Distant Touch | ••• | 80 | rated |
| Stamp of Ultimate Authority | •• | 80 | — |
| The Ultimate Document | ••• | 80 | — |
| Resplendent Dolphin Courier | •••• | 81 | — |

### `cult` — Cult of the Illuminated (5)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Golden Bird of Sunlight | ••• | 69 | — |
| The Holy Writ of Twilight | ••• | 69 | — |
| The Tears of the Harvest | ••• | 69 | — |
| Cry of the Illuminated | ••••• | 70 | — |
| Shining Daiklave of Darkness | •••• | 70 | — |

### `halt` — Kingdom of Halta (5)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Cold Wind Knives | •••• | 93 | — |
| Iron Puzzle Box | n/A | 93 | — |
| Raptor’s Wings | ••• | 94 | — |
| Sky Cutter | •• | 95 | — |
| Soul-Heart | • | 95 | — |

### `svnt` — Savant & Sorcerer (5)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Collar of Cleansing Light | • | 40 | — |
| Mask | •• | 41 | — |
| Ring of Being | •••• | 41 | — |
| Wings of the Raptor | •••• | 42 | — |
| Soul Mirror | ••••• | 43 | — |

### `side` — Sidereals (3)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Aerial Rickshaw | •••• | 24 | — |
| Cage of Eternal Torment | •••• | 39 | — |
| Collar of Dutiful Submission | ••••• | 39 | — |

### `coin` — Manacle and Coin ⚠ (1)

| Name | Rating | Page(s) | Build |
|---|---|---|---|
| Winterbreath Jar | • | 31 | — |
