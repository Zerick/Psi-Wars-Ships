/* =============================================================================
   Mock Data — Drives all UI components during Phase 2
   Replace with real API calls in Phase 6
   ============================================================================= */

export const MOCK_SHIPS = [
  {
    ship_id: "ship_1",
    template_id: "wildcat_v1",
    display_name: "Red Fox",
    faction: "Empire",
    control: "human",
    sm: 5,
    ship_class: "fighter",
    st_hp: 120,
    current_hp: 95,
    wound_level: "minor",
    is_destroyed: false,
    ht: "13",
    hnd: 2,
    sr: 4,
    accel: 10,
    top_speed: 400,
    stall_speed: 60,
    dr_front: 50,
    dr_rear: 25,
    dr_left: 25,
    dr_right: 25,
    dr_top: 25,
    dr_bottom: 25,
    fdr_max: 0,
    current_fdr: 0,
    force_screen_type: "none",
    ecm_rating: -4,
    targeting_bonus: 5,
    has_tactical_esm: true,
    has_decoy_launcher: true,
    disabled_systems: [],
    destroyed_systems: [],
    emergency_power_reserves: 0,
    weapons: [
      {
        name: "SP74-TR Heavy Plasma Gatling",
        damage_str: "6d×15(2) burn ex",
        acc: 6,
        rof: 8,
        weapon_type: "beam",
        armor_divisor: 2.0,
        mount: "fixed_front",
        range_str: "3 mi/8 mi",
        is_explosive: true
      },
      {
        name: "Light Blaster Cannon",
        damage_str: "3d×5(5) burn",
        acc: 6,
        rof: 4,
        weapon_type: "beam",
        armor_divisor: 5.0,
        mount: "wing_left",
        range_str: "2 mi/6 mi",
        is_explosive: false
      }
    ],
    pilot: {
      name: "Ace McFly",
      piloting_skill: 16,
      gunnery_skill: 14,
      basic_speed: 7.0,
      is_ace_pilot: true,
      luck_level: "luck",
      current_fp: 10,
      max_fp: 10
    },
    source_url: "https://psi-wars.wikidot.com/wiki:wildcat"
  },
  {
    ship_id: "ship_2",
    template_id: "tempest_v1",
    display_name: "Blue Jay",
    faction: "Alliance",
    control: "npc",
    sm: 4,
    ship_class: "fighter",
    st_hp: 70,
    current_hp: 52,
    wound_level: "major",
    is_destroyed: false,
    ht: "12",
    hnd: 3,
    sr: 5,
    accel: 20,
    top_speed: 800,
    stall_speed: 100,
    dr_front: 30,
    dr_rear: 15,
    dr_left: 15,
    dr_right: 15,
    dr_top: 15,
    dr_bottom: 15,
    fdr_max: 0,
    current_fdr: 0,
    force_screen_type: "none",
    ecm_rating: -4,
    targeting_bonus: 5,
    has_tactical_esm: true,
    has_decoy_launcher: false,
    disabled_systems: ["sensors"],
    destroyed_systems: [],
    emergency_power_reserves: 0,
    weapons: [
      {
        name: "Twin Laser Cannons",
        damage_str: "5d×5(2) burn",
        acc: 9,
        rof: 4,
        weapon_type: "beam",
        armor_divisor: 2.0,
        mount: "fixed_front",
        range_str: "5 mi/15 mi",
        is_explosive: false
      }
    ],
    pilot: {
      name: "NPC Pilot",
      piloting_skill: 13,
      gunnery_skill: 12,
      basic_speed: 6.0,
      is_ace_pilot: false,
      luck_level: "none",
      current_fp: 8,
      max_fp: 10
    },
    source_url: null
  },
  {
    ship_id: "ship_3",
    template_id: "tigershark_v1",
    display_name: "Iron Maw",
    faction: "Empire",
    control: "npc",
    sm: 8,
    ship_class: "corvette",
    st_hp: 400,
    current_hp: 400,
    wound_level: "none",
    is_destroyed: false,
    ht: "14",
    hnd: 1,
    sr: 5,
    accel: 6,
    top_speed: 250,
    stall_speed: 0,
    dr_front: 1000,
    dr_rear: 400,
    dr_left: 400,
    dr_right: 400,
    dr_top: 400,
    dr_bottom: 400,
    fdr_max: 750,
    current_fdr: 580,
    force_screen_type: "hardened",
    ecm_rating: -4,
    targeting_bonus: 5,
    has_tactical_esm: true,
    has_decoy_launcher: true,
    disabled_systems: [],
    destroyed_systems: [],
    emergency_power_reserves: 15,
    weapons: [
      {
        name: "Heavy Turbolaser Battery",
        damage_str: "6d×70(5) burn ex",
        acc: 6,
        rof: 3,
        weapon_type: "beam",
        armor_divisor: 5.0,
        mount: "turret_dorsal",
        range_str: "10 mi/30 mi",
        is_explosive: true
      },
      {
        name: "Point Defense Array",
        damage_str: "3d×3(5) burn",
        acc: 6,
        rof: 20,
        weapon_type: "beam",
        armor_divisor: 5.0,
        mount: "turret_ventral",
        range_str: "1 mi/3 mi",
        is_explosive: false
      }
    ],
    pilot: {
      name: "Cpt. Voss",
      piloting_skill: 14,
      gunnery_skill: 15,
      basic_speed: 6.5,
      is_ace_pilot: false,
      luck_level: "none",
      current_fp: 12,
      max_fp: 12
    },
    source_url: null
  },
  {
    ship_id: "ship_4",
    template_id: "valkyrie_v1",
    display_name: "Wraith",
    faction: "Alliance",
    control: "human",
    sm: 5,
    ship_class: "fighter",
    st_hp: 100,
    current_hp: 0,
    wound_level: "destroyed",
    is_destroyed: true,
    ht: "12",
    hnd: 3,
    sr: 5,
    accel: 15,
    top_speed: 600,
    stall_speed: 80,
    dr_front: 70,
    dr_rear: 35,
    dr_left: 35,
    dr_right: 35,
    dr_top: 35,
    dr_bottom: 35,
    fdr_max: 300,
    current_fdr: 0,
    force_screen_type: "hardened",
    ecm_rating: -5,
    targeting_bonus: 6,
    has_tactical_esm: true,
    has_decoy_launcher: true,
    disabled_systems: ["propulsion", "weapons", "sensors"],
    destroyed_systems: ["reactor"],
    emergency_power_reserves: 0,
    weapons: [
      {
        name: "Plasma Lance",
        damage_str: "6d×20(2) burn ex",
        acc: 9,
        rof: 1,
        weapon_type: "beam",
        armor_divisor: 2.0,
        mount: "fixed_front",
        range_str: "4 mi/12 mi",
        is_explosive: true
      }
    ],
    pilot: {
      name: "Lt. Kira",
      piloting_skill: 15,
      gunnery_skill: 14,
      basic_speed: 7.25,
      is_ace_pilot: true,
      luck_level: "extraordinary_luck",
      current_fp: 0,
      max_fp: 10
    },
    source_url: null
  }
];

export const MOCK_ENGAGEMENTS = [
  {
    ship_a_id: "ship_1",
    ship_b_id: "ship_2",
    range_band: "medium",
    advantage: "ship_1",
    matched_speed: true,
    hugging: null
  },
  {
    ship_a_id: "ship_3",
    ship_b_id: "ship_2",
    range_band: "long",
    advantage: null,
    matched_speed: false,
    hugging: null
  }
];

export const MOCK_COMBAT_LOG = [
  { message: "══════ TURN 1 ══════", event_type: "turn", turn: 1 },
  { message: "Red Fox declares Move and Attack (pursue)", event_type: "info", turn: 1 },
  { message: "Blue Jay declares Evade", event_type: "info", turn: 1 },
  { message: "Chase: Red Fox (Piloting-16 +2 Hnd) vs Blue Jay (Piloting-13 +3 Hnd)", event_type: "chase", turn: 1 },
  { message: "Red Fox rolls 3d6: [3, 5, 2] = 10 vs 18 — succeeds by 8", event_type: "chase", turn: 1 },
  { message: "Blue Jay rolls 3d6: [6, 4, 6] = 16 vs 16 — succeeds by 0", event_type: "chase", turn: 1 },
  { message: "Red Fox wins chase by 8! Chooses: Advantage + Match Speed", event_type: "chase", turn: 1 },
  { message: "Red Fox fires SP74-TR Heavy Plasma Gatling at Blue Jay", event_type: "attack", turn: 1 },
  { message: "  Gunnery-14, +6 Acc, +5 Lock, -7 Range, -3 Speed, +1 RoF = effective 16", event_type: "info", turn: 1 },
  { message: "Attack roll: 3d6 [4, 2, 3] = 9 vs 16 — HIT by 7", event_type: "attack", turn: 1 },
  { message: "Blue Jay dodges! Piloting/2 + Hnd = 8", event_type: "info", turn: 1 },
  { message: "Dodge roll: 3d6 [5, 6, 3] = 14 vs 8 — FAILS", event_type: "defense_fail", turn: 1 },
  { message: "Damage: 6d×15(2) burn ex → 34 × 15 = 510, AD(2) → effective 255 vs DR 15", event_type: "damage", turn: 1 },
  { message: "Blue Jay takes 240 penetrating damage — MAJOR WOUND", event_type: "damage", turn: 1 },
  { message: "  Sensors DISABLED from subsystem cascade", event_type: "system_damage", turn: 1 },
  { message: "Blue Jay HT check (major wound): 3d6 [3, 4, 2] = 9 vs 12 — remains operational", event_type: "info", turn: 1 },
  { message: "══════ TURN 2 ══════", event_type: "turn", turn: 2 },
  { message: "Red Fox declares Attack", event_type: "info", turn: 2 },
  { message: "Blue Jay declares Evade", event_type: "info", turn: 2 },
  { message: "[NPC] Blue Jay AI: Threat HIGH, HP critical. Priority: survive. Choosing Evade.", event_type: "npc_reasoning", turn: 2 },
  { message: "Iron Maw fires Heavy Turbolaser Battery at Blue Jay", event_type: "attack", turn: 2 },
  { message: "  Gunnery-15, +6 Acc, +5 Lock, -11 Range, -4 SM diff = effective 11", event_type: "info", turn: 2 },
  { message: "Attack roll: 3d6 [6, 6, 5] = 17 vs 11 — MISS", event_type: "attack", turn: 2 },
  { message: "Iron Maw's Force Screen absorbs 170 damage (580 → 410 fDR remaining)", event_type: "force_screen", turn: 2 },
];

export const MOCK_DICE_LOG = [
  { ship: "Red Fox", context: "Chase", expression: "3d6", rolls: [3, 5, 2], total: 10, target: 18, success: true, margin: 8, is_npc: false },
  { ship: "Blue Jay", context: "Chase", expression: "3d6", rolls: [6, 4, 6], total: 16, target: 16, success: true, margin: 0, is_npc: true },
  { ship: "Red Fox", context: "Attack", expression: "3d6", rolls: [4, 2, 3], total: 9, target: 16, success: true, margin: 7, is_npc: false },
  { ship: "Blue Jay", context: "Dodge", expression: "3d6", rolls: [5, 6, 3], total: 14, target: 8, success: false, margin: -6, is_npc: true },
  { ship: "Red Fox", context: "Damage", expression: "6d6", rolls: [5, 6, 4, 6, 6, 5], total: 34, target: null, success: null, margin: null, is_npc: false },
  { ship: "Blue Jay", context: "HT Check", expression: "3d6", rolls: [3, 4, 2], total: 9, target: 12, success: true, margin: 3, is_npc: true },
  { ship: "Iron Maw", context: "Attack", expression: "3d6", rolls: [6, 6, 5], total: 17, target: 11, success: false, margin: -6, is_npc: true },
];

// Currently active ship for highlight testing
export const MOCK_ACTIVE_STATE = {
  active_ship_id: "ship_1",
  targets: ["ship_2"],       // ships the active ship is targeting
  targeting: ["ship_3"],     // ships that are targeting the active ship (for this test, none really, but adding for demo)
  current_turn: 2
};
