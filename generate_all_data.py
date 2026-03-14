"""
Comprehensive M3 data generator.

Creates all remaining weapon catalog entries, module catalog entries,
and ship template JSONs from the Psi-Wars source material.

Run from the project root:
    python3 generate_all_data.py
"""
import json
import os
from pathlib import Path

WEAPONS_DIR = Path("tests/fixtures/weapons")
MODULES_DIR = Path("tests/fixtures/modules")
SHIPS_DIR = Path("tests/fixtures/ships")

def save_json(directory: Path, filename: str, data: dict):
    path = directory / filename
    if not path.exists():
        path.write_text(json.dumps(data, indent=2))
        print(f"  Created: {path}")
    else:
        print(f"  Exists:  {path}")


def make_weapon(weapon_id, name, damage, acc, range_str, rof, rcl, shots,
                ewt, st_req="M", bulk="-10", weapon_type="beam",
                damage_type="burn", armor_divisor=None, notes="", tags=None):
    return {
        "weapon_id": weapon_id,
        "name": name,
        "damage": damage,
        "acc": acc,
        "range": range_str,
        "rof": str(rof),
        "rcl": rcl,
        "shots": str(shots),
        "ewt": str(ewt),
        "st_requirement": st_req,
        "bulk": bulk,
        "weapon_type": weapon_type,
        "damage_type": damage_type,
        "armor_divisor": armor_divisor,
        "notes": notes,
        "tags": tags or [],
        "version": "1.0.0"
    }


def make_ship(template_id, name, faction, sm, ship_class,
              st_hp, ht, hnd, sr, accel, top_speed, stall_speed,
              afterburner, dr_front, dr_rear, dr_left, dr_right,
              dr_top, dr_bottom, dr_material, fdr_max, fs_type,
              electronics, occ_raw, loc_raw, logistics,
              traits, modes, weapons, module_slots=None,
              craft_complement=None, description="", tags=None, source_url=None):
    return {
        "template_id": template_id,
        "version": "1.0.0",
        "name": name,
        "faction_origin": faction,
        "sm": sm,
        "ship_class": ship_class,
        "attributes": {"st_hp": st_hp, "ht": ht, "hnd": hnd, "sr": sr},
        "mobility": {"accel": accel, "top_speed": top_speed, "stall_speed": stall_speed},
        "afterburner": afterburner,
        "defense": {
            "dr_front": dr_front, "dr_rear": dr_rear,
            "dr_left": dr_left, "dr_right": dr_right,
            "dr_top": dr_top, "dr_bottom": dr_bottom,
            "dr_material": dr_material,
            "fdr_max": fdr_max, "force_screen_type": fs_type
        },
        "electronics": electronics,
        "occ_raw": occ_raw,
        "loc_raw": loc_raw,
        "logistics": logistics,
        "traits": traits,
        "modes": modes,
        "weapons": weapons,
        "module_slots": module_slots or [],
        "craft_complement": craft_complement or [],
        "description": description,
        "tags": tags or [faction, ship_class],
        "source_url": source_url
    }


def wpn_mount(weapon_ref, mount="fixed_front", linked=1, arc="front", notes=""):
    return {"weapon_ref": weapon_ref, "mount": mount,
            "linked_count": linked, "arc": arc, "notes": notes}


# Standard electronics blocks
def std_electronics(ecm=-4, targeting=5, scanner=30, decoy=True, esm=True,
                    scrambler=False, neural=False, comm=1000, ftl=None, notes=""):
    return {
        "ultrascanner_range": scanner, "targeting_bonus": targeting,
        "ecm_rating": ecm, "night_vision": 9, "comm_range": comm,
        "ftl_comm_range": ftl, "has_decoy_launcher": decoy,
        "has_tactical_esm": esm, "has_distortion_scrambler": scrambler,
        "has_neural_interface": neural,
        "sensor_notes": notes or "Medium Tactical Ultra-Scanner; Distortion Jammer"
    }

def obsolete_electronics(ecm=-2, targeting=4, notes=""):
    return {
        "ultrascanner_range": 30, "targeting_bonus": targeting,
        "ecm_rating": ecm, "night_vision": 9, "comm_range": 10000,
        "ftl_comm_range": None, "has_decoy_launcher": False,
        "has_tactical_esm": True, "has_distortion_scrambler": False,
        "has_neural_interface": False,
        "sensor_notes": notes or "Obsolete Medium Tactical Ultra-Scanner; Obsolete Distortion Jammer; -2 contested EO rolls"
    }

def capital_electronics(ecm=-4, targeting=5, scanner=4000, comm=10000, ftl=300, scrambler=True, notes=""):
    return {
        "ultrascanner_range": scanner, "targeting_bonus": targeting,
        "ecm_rating": ecm, "night_vision": 9, "comm_range": comm,
        "ftl_comm_range": ftl, "has_decoy_launcher": False,
        "has_tactical_esm": False, "has_distortion_scrambler": scrambler,
        "has_neural_interface": False,
        "sensor_notes": notes or "Capital-Scale Tactical Ultra-Scanner; Large Area Jammer; Distortion Scrambler"
    }

def redjack_corvette_electronics(ecm=-4, notes=""):
    return {
        "ultrascanner_range": 150, "targeting_bonus": 5,
        "ecm_rating": ecm, "night_vision": 9, "comm_range": 10000,
        "ftl_comm_range": 30, "has_decoy_launcher": False,
        "has_tactical_esm": True, "has_distortion_scrambler": False,
        "has_neural_interface": False,
        "sensor_notes": notes or "Ultrascanner Open Mount 150mi search/15mi scan; LPI; Distortion Jammer; Large FTL Comm 30 parsec"
    }


def std_afterburner(accel, top_speed, hnd_mod=0, range_override=None, high_g=False):
    return {"accel": accel, "top_speed": top_speed, "hnd_mod": hnd_mod,
            "fuel_multiplier": 4.0, "range_override": range_override, "is_high_g": high_g}


def std_logistics(lwt, load, range_miles, cost, hyper=None, jumps=None, endurance=None, sig_cost=None):
    return {"lwt": lwt, "load": load, "range_miles": range_miles, "cost": cost,
            "hyperdrive_rating": hyper, "jump_capacity": jumps,
            "endurance": endurance, "signature_cost": sig_cost}


def generate_weapons():
    """Generate all weapon catalog entries."""
    print("\n=== GENERATING WEAPONS ===")

    weapons = [
        make_weapon("gatling_blaster", "Gatling Blaster", "6d×5(5) burn", 9, "2700/8000",
                     12, 2, "200/Fp", "1600", weapon_type="beam", armor_divisor="(5)",
                     tags=["imperial", "fighter_scale", "beam", "gatling"]),
        make_weapon("arc_gatling_blaster", "ARC Gatling Blaster", "6d×5(5) burn", 9, "2700/8000",
                     12, 2, "200/Fp", "1600", weapon_type="beam", armor_divisor="(5)",
                     tags=["arc", "fighter_scale", "beam", "gatling"]),
        make_weapon("160mm_plasma_lance_missile", "160mm Plasma Lance Missile", "6d×30(10) burn",
                     3, "1000/25 mi", 1, 1, "8", "200", st_req="23M", bulk="-11",
                     weapon_type="missile", damage_type="burn", armor_divisor="(10)",
                     tags=["missile", "plasma_lance", "fighter_scale"]),
        make_weapon("160mm_plasma_missile", "160mm Plasma Burst Missile", "6d×15 burn ex",
                     3, "1000/25 mi", 1, 1, "8", "200", st_req="23M", bulk="-11",
                     weapon_type="missile", damage_type="burn_ex",
                     tags=["missile", "plasma", "fighter_scale"]),
        make_weapon("100mm_plasma_lance_missile", "100mm Plasma Lance Missile", "6d×20(10) burn",
                     3, "2000/10000", 1, 1, "6", "25", st_req="11B", bulk="-8",
                     weapon_type="missile", damage_type="burn", armor_divisor="(10)",
                     tags=["missile", "plasma_lance", "light"]),
        make_weapon("100mm_plasma_missile", "100mm Plasma Missile", "6d×10 burn ex",
                     3, "2000/10000", 1, 1, "6", "25", st_req="11B", bulk="-8",
                     weapon_type="missile", damage_type="burn_ex",
                     tags=["missile", "plasma", "light"]),
        make_weapon("400mm_isomeric_torpedo", "400mm Isomeric Torpedo", "5d×200 cr ex",
                     3, "300/10 mi", 1, 1, "1", "2500", st_req="150M", bulk="-15",
                     weapon_type="torpedo", damage_type="cr_ex",
                     notes="Unguided. Uses Gunner (Torpedo).",
                     tags=["torpedo", "isomeric", "fighter_scale"]),
        make_weapon("quad_repeater_cannon", "Quad Repeater Cannon", "6d×4(5) burn",
                     8, "1000/3000", 8, 2, "400/Fp", "1000",
                     weapon_type="beam", armor_divisor="(5)",
                     tags=["beam", "repeater", "obsolete"]),
        make_weapon("fighter_blaster_cannon", "Fighter-Scale Blaster Cannon", "6d×5(5) burn",
                     9, "1 mi/3 mi", 8, 2, "200", "1200",
                     weapon_type="beam", armor_divisor="(5)",
                     notes="Vespa variant of Hornet-style cannon.",
                     tags=["beam", "fighter_scale"]),
        make_weapon("corvette_scale_cannon", "Corvette-Scale Cannon", "6d×30(5) burn",
                     9, "10 mi/30 mi", 1, 3, "NA", "25t",
                     weapon_type="beam", armor_divisor="(5)",
                     tags=["beam", "corvette_scale"]),
        make_weapon("corvette_muonic_cannon", "Corvette-Scale Muonic Cannon", "6d×20(10) burn",
                     9, "15 mi/45 mi", 3, 2, "100", "80t",
                     weapon_type="beam", armor_divisor="(10)",
                     tags=["beam", "corvette_scale", "muonic"]),
        make_weapon("sc4tr_plasma_gatling", "SC4-TR Plasma Gatling", "6d×8(2) burn ex",
                     6, "3 mi/10 mi", 8, 3, "160/F", "1200",
                     weapon_type="plasma", damage_type="burn_ex", armor_divisor="(2)",
                     tags=["redjack", "plasma", "gatling", "fighter_scale"]),
        make_weapon("ramming_prow", "Ramming Prow", "6d×4 cr", 0, "collision", 1, 1, "NA", "0",
                     weapon_type="ram", damage_type="cr",
                     notes="Requires collision range. Facing: F.",
                     tags=["ram", "melee"]),
        make_weapon("internal_torpedo_400mm", "400mm Internal Torpedo", "5d×200 cr ex",
                     0, "collision", 1, 1, "1", "2500",
                     weapon_type="torpedo", damage_type="cr_ex",
                     notes="Internal mount. Collision range only. Single use.",
                     tags=["torpedo", "internal", "single_use"]),
        make_weapon("anti_personnel_blaster", "Anti-Personnel Blaster Cannon", "10d(5) burn",
                     9, "600/1800", 3, 2, "540/Fp", "45", st_req="16M",
                     weapon_type="beam", armor_divisor="(5)",
                     notes="ROF 12 when linked (x4). Designed for anti-personnel use.",
                     tags=["beam", "anti_personnel"]),
        make_weapon("fighter_cannon_generic", "Fighter Cannon", "6d×5(5) burn",
                     9, "2700/8000", 3, 2, "200/Fp", "1000", st_req="75M",
                     weapon_type="beam", armor_divisor="(5)",
                     notes="Generic fighter-scale blaster cannon.",
                     tags=["beam", "fighter_scale"]),
        make_weapon("lightning_cannon", "Lightning Cannon", "6d×30(5) burn sur arc",
                     6, "2000/6000", "1/30", 2, "NA", "NA",
                     weapon_type="beam", damage_type="burn_sur",
                     armor_divisor="(5)",
                     notes="Relic weapon. ROF 1/30 (fires once per 30 turns). Surge effect. May only fire within visual range. Pilot rolls better of Gunner or psionic skill.",
                     tags=["arc", "relic", "psionic", "lightning"]),
        make_weapon("disruptor_cannon", "Disruptor Cannon", "6d×75(5) sur",
                     9, "60 mi/180 mi", 15, 2, "15", "500t",
                     weapon_type="beam", damage_type="sur",
                     armor_divisor="(5)",
                     notes="Surge damage. Designed to disable rather than destroy.",
                     tags=["imperial", "disruptor", "surge", "capital_scale"]),
        make_weapon("isomeric_heavy_torpedo", "Isomeric Heavy Torpedo", "5d×300 cr ex",
                     3, "150/100 mi", 1, 1, "4", "30t", st_req="M", bulk="-20",
                     weapon_type="torpedo", damage_type="cr_ex",
                     notes="Heavy torpedo variant. Unguided.",
                     tags=["torpedo", "isomeric", "heavy"]),
        make_weapon("mauler_beam", "Mauler Beam", "5d×100 cr",
                     9, "1 mi/3 mi", 1, 2, "NA", "30T",
                     weapon_type="beam", damage_type="cr",
                     notes="Short-range crushing beam weapon.",
                     tags=["rath", "beam", "capital_scale"]),
        make_weapon("guillotine_weapon", "Guillotine", "6d×100(5) cut",
                     0, "collision", 1, 1, "NA", "500",
                     weapon_type="ram", damage_type="cut",
                     notes="Close-range cutting weapon. Collision range only.",
                     tags=["rath", "melee", "capital_scale"]),
        make_weapon("pulsar_super_cannon", "Pulsar Super-Cannon", "6d×600(3) burn ex",
                     6, "1000 mi/3000 mi", "1/10", 3, "10", "15t",
                     weapon_type="beam", damage_type="burn_ex",
                     armor_divisor="(3)",
                     notes="ROF 1/10. Super-weapon class. Extreme range artillery.",
                     tags=["imperial", "super_weapon", "capital_scale"]),
        make_weapon("spire_plasma_cannon", "Spire-Scale Plasma Cannon", "6d×200(2) burn ex",
                     9, "100 mi/300 mi", "1/10", 3, "NA", "850t",
                     weapon_type="plasma", damage_type="burn_ex",
                     armor_divisor="(2)",
                     notes="ROF 1/10. Massive plasma weapon.",
                     tags=["rath", "plasma", "capital_scale"]),
        make_weapon("trader_capital_cannon", "Trader Capital-Scale Cannon", "6d×40(10) burn sur",
                     9, "35 mi/90 mi", 4, 2, "NA", "500t",
                     weapon_type="beam", damage_type="burn_sur",
                     armor_divisor="(10)",
                     notes="Trader-tech muonic capital weapon. Surge effect.",
                     tags=["trader", "capital_scale", "muonic", "surge"]),
        make_weapon("spinal_pulsar", "Spinal Pulsar", "6d×1200(3) burn ex",
                     9, "100 mi", "1/10", 2, "5", "250kt",
                     weapon_type="beam", damage_type="burn_ex",
                     armor_divisor="(3)",
                     notes="Spinal mount super-weapon. ROF 1/10.",
                     tags=["trader", "super_weapon", "spinal"]),
        make_weapon("spinal_blaster", "Spinal Blaster", "6d×600(5) burn",
                     9, "100 mi", "1/10", 2, "5", "250kt",
                     weapon_type="beam", armor_divisor="(5)",
                     notes="Spinal mount. ROF 1/10.",
                     tags=["trader", "super_weapon", "spinal"]),
        make_weapon("spinal_muonic_blaster", "Spinal Muonic Blaster", "6d×300(10) burn sur",
                     9, "100 mi", "1/10", 2, "5", "250kt",
                     weapon_type="beam", damage_type="burn_sur",
                     armor_divisor="(10)",
                     notes="Spinal mount muonic. ROF 1/10. Surge effect.",
                     tags=["trader", "super_weapon", "spinal", "muonic"]),
        make_weapon("super_heavy_muonic_cannon", "Super-Heavy Muonic Cannon", "6d×70(10) burn sur",
                     9, "170 mi/500 mi", 3, 2, "NA", "5000t",
                     weapon_type="beam", damage_type="burn_sur",
                     armor_divisor="(10)",
                     notes="Trader-tech super-heavy turret weapon. Surge effect.",
                     tags=["trader", "super_heavy", "muonic", "surge"]),
        make_weapon("capital_muonic_cannon", "Capital-Scale Muonic Cannon", "6d×35(10) burn sur",
                     9, "60 mi/180 mi", 4, 2, "NA", "500t",
                     weapon_type="beam", damage_type="burn_sur",
                     armor_divisor="(10)",
                     notes="Trader-tech capital turret. Surge effect.",
                     tags=["trader", "capital_scale", "muonic", "surge"]),
        # Module weapons (also used standalone on some ships)
        make_weapon("zip3r_blaster_gatling", "ZIP-3R Light Blaster Gatling", "6d×4(5) burn",
                     9, "2 mi/5 mi", 16, 2, "200/F", "1200",
                     weapon_type="beam", armor_divisor="(5)",
                     notes="Popular Redjack fighter weapon. High ROF, good penetration.",
                     tags=["redjack", "beam", "gatling", "fighter_scale"]),
        make_weapon("ban6_plasma_cannon", "BAN-6 Plasma Cannon", "5d×20(2) burn ex",
                     6, "2 mi/10 mi", "1/3", 3, "15/3E", "1200",
                     weapon_type="plasma", damage_type="burn_ex", armor_divisor="(2)",
                     notes="Lighter B00-M variant. Same overheating rules: risks overheating after 3 shots.",
                     tags=["redjack", "plasma", "fighter_scale"]),
        make_weapon("msml_plasma_burst_missile_160", "160mm MSML Plasma Burst Missile", "6d×15 burn ex",
                     4, "1000/30 mi", 1, 1, "4", "1200", st_req="M", bulk="-15",
                     weapon_type="missile", damage_type="burn_ex",
                     tags=["missile", "plasma", "redjack"]),
        make_weapon("msml_plasma_lance_missile_160", "160mm MSML Plasma Lance Missile", "6d×30(10) burn ex",
                     4, "1000/30 mi", 1, 1, "4", "1200", st_req="M", bulk="-15",
                     weapon_type="missile", damage_type="burn_ex", armor_divisor="(10)",
                     tags=["missile", "plasma_lance", "redjack"]),
        make_weapon("min3r_mining_laser", "MIN-3R Mining Laser", "5d×15(10) cut inc",
                     12, "500/3 mi", 1, 1, "25/5E", "4000",
                     weapon_type="mining_laser", damage_type="cut_inc", armor_divisor="(10)",
                     notes="Designed for asteroid mining. Effective against slow, armored targets.",
                     tags=["redjack", "mining", "laser"]),
        make_weapon("sp74tr_heavy_plasma_gatling", "SP74-TR Heavy Plasma Gatling", "6d×15(2) burn ex",
                     6, "3 mi/8 mi", 8, 3, "88/3F", "4000",
                     weapon_type="plasma", damage_type="burn_ex", armor_divisor="(2)",
                     notes="Saturation fire weapon. Can aim at spot near target for +4 to hit but loses armor divisor.",
                     tags=["redjack", "plasma", "gatling"]),
        make_weapon("isomeric_torpedo_bay_single", "Isomeric Torpedo Bay (Single)", "5d×200 cr ex",
                     3, "300/10 mi", 1, 1, "1", "2500", st_req="150M", bulk="-15",
                     weapon_type="torpedo", damage_type="cr_ex",
                     notes="Single-shot torpedo bay. Replaces main weapon slot. 30 min reload.",
                     tags=["torpedo", "single_use", "redjack"]),
        # Tractor beams
        make_weapon("tractor_beam_st160", "ST 160 Tractor Beam", "0",
                     0, "1000/3000", 1, 1, "NA", "2000",
                     weapon_type="tractor", damage_type="special",
                     notes="ST 160 tractor beam. Range 3000, Move 10.",
                     tags=["tractor", "utility"]),
        make_weapon("tractor_beam_st1000", "ST 1000 Tractor Beam", "0",
                     0, "2000", 1, 1, "NA", "10000",
                     weapon_type="tractor", damage_type="special",
                     notes="ST 1000 tractor beam. Range 2000, Move 10. Capital-scale.",
                     tags=["tractor", "utility", "capital_scale"]),
    ]

    for w in weapons:
        save_json(WEAPONS_DIR, f"{w['weapon_id']}.json", w)


def generate_ships():
    """Generate all remaining ship template JSONs."""
    print("\n=== GENERATING SHIPS ===")

    ships = []

    # --- FIGHTERS (SM 4-5) ---

    ships.append(make_ship(
        "drifter_class_racer_v1", "Drifter Class Racer", "redjack", 4, "racer",
        80, "12", 4, 3, 25, 750, 55,
        std_afterburner(40, 850, range_override=3000),
        15, 15, 15, 15, 15, 15, "carbide_composite", 0, "none",
        std_electronics(ecm=0, decoy=True, esm=True,
                        notes="No combat electronics by default (ECM 0). Optional combat package adds scanner, targeting +5, ECM -4, decoys."),
        "1S+1rx", "g2Wi3rR",
        std_logistics(6.5, 2.5, 12000, "$3.5M", sig_cost=5),
        ["double_dr_vs_plasma", "double_dr_vs_shaped_charge", "ejection_seat", "modular"],
        {},
        [],
        module_slots=[
            {"slot_id": "engine", "slot_type": "engine", "weight_class": "any", "max_weight": 6000.0,
             "notes": "Modular engine. Default: Plasma Thruster. Alternatives: Next Gen, Hyperium, Plasma Fan."},
            {"slot_id": "main_weapon", "slot_type": "weapon", "weight_class": "any", "max_weight": 1200.0,
             "notes": "Underslung weapon mount, rated 1200 lbs."},
            {"slot_id": "wing_left", "slot_type": "weapon", "weight_class": "any", "max_weight": 600.0,
             "notes": "Left wing hardpoint. Missiles, fuel, or thruster pods."},
            {"slot_id": "wing_right", "slot_type": "weapon", "weight_class": "any", "max_weight": 600.0,
             "notes": "Right wing hardpoint. Missiles, fuel, or thruster pods."},
            {"slot_id": "accessory", "slot_type": "accessory", "weight_class": "any", "max_weight": 1650.0,
             "notes": "Behind cockpit. Silverfish force screen, Hyperlight hyperdrive, or Longstrider fuel."},
        ],
        description="A cockpit strapped to a great array of engines. Galaxy-famous racer design.",
        tags=["redjack", "racer", "modular"],
        source_url="https://psi-wars.wikidot.com/drifter-class-racer"
    ))

    ships.append(make_ship(
        "flanker_class_fighter_v1", "Flanker Class Fighter", "empire", 5, "fighter",
        105, "11f", 2, 4, 10, 500, 45,
        std_afterburner(13, 700, range_override=6000),
        50, 50, 50, 50, 50, 50, "cerablate", 100, "standard",
        std_electronics(ecm=-6, notes="Medium Tactical Ultra-Scanner; Distortion Jammer -6; Stealth coating; Decoy Launcher; Tactical ESM"),
        "2SV", "g2Wi3rR",
        std_logistics(13.0, 3.6, 24000, "$8M", hyper=1, jumps=1, sig_cost=5),
        ["ablative_armor", "stealth_coating"],
        {},
        [wpn_mount("gatling_blaster", "fixed_front", 2, "front", "Two linked gatling blasters. Total ROF 24 (+4)."),
         wpn_mount("160mm_plasma_lance_missile", "wing_left", 1, "front", "Wing-mounted missile bay, 8 missiles."),
         wpn_mount("160mm_plasma_missile", "wing_right", 1, "front", "Wing-mounted missile bay, 8 missiles.")],
        description="A stealthy Imperial fighter with cerablate armor. Two crew: pilot and gunner/systems operator.",
        source_url="https://psi-wars.wikidot.com/flanker-class-fighter"
    ))

    ships.append(make_ship(
        "peltast_class_striker_v1", "Peltast Class Striker", "empire", 4, "striker",
        85, "10f", 4, 3, 10, 450, 50,
        std_afterburner(15, 550, range_override=5500),
        15, 15, 15, 15, 15, 15, None, 0, "none",
        std_electronics(notes="Medium Tactical Ultra-Scanner; Distortion Jammer; Decoy; ESM"),
        "1S", "g3rR2Wi",
        std_logistics(7.2, 3.0, 22000, "$2.25M", sig_cost=5),
        ["ejection_seat", "contragravity_stall_reduction"],
        {},
        [wpn_mount("imperial_fighter_blaster", "fixed_front", 2, "front", "Two linked blasters. Total ROF 6 (+1)."),
         wpn_mount("160mm_plasma_lance_missile", "wing_left", 1, "front", "6 missiles per wing rack."),
         wpn_mount("400mm_isomeric_torpedo", "fixed_front", 1, "front", "Single torpedo, internal bay.")],
        description="An Imperial strike fighter. Wings include contragravity that reduces stall to 20.",
        source_url="https://psi-wars.wikidot.com/peltast-class-striker"
    ))

    ships.append(make_ship(
        "piranha_class_fighter_v1", "Piranha Class Fighter", "rath", 4, "fighter",
        105, "9f", 1, 4, 10, 400, 85,
        std_afterburner(15, 500, range_override=4500),
        50, 25, 25, 25, 50, 25, "nanopolymer", 0, "none",
        obsolete_electronics(notes="Obsolete Ultra-Scanner; Obsolete Targeting +4; Obsolete Distortion Jammer -2; Tactical ESM"),
        "1SV", "g3rR2Wi",
        std_logistics(9.0, 3.6, 18000, "$2.5M"),
        ["double_dr_vs_plasma", "obsolete_electronics"],
        {},
        [wpn_mount("quad_repeater_cannon", "turret", 1, "all", "Single turret-mounted quad repeater."),
         wpn_mount("160mm_plasma_lance_missile", "wing_left", 1, "front", "8 missiles."),
         wpn_mount("160mm_plasma_missile", "wing_right", 1, "front", "8 missiles.")],
        description="A Rath Industries fighter with obsolete but rugged electronics. DR 50 front/bottom, 25 elsewhere.",
        tags=["rath", "fighter"],
        source_url="https://psi-wars.wikidot.com/piranha-class-fighter"
    ))

    ships.append(make_ship(
        "tempest_class_interceptor_v1", "Tempest Class Interceptor", "empire", 4, "interceptor",
        85, "11f", 5, 3, 25, 800, 40,
        std_afterburner(35, 1000, range_override=4000, high_g=True),
        10, 10, 10, 10, 10, 10, "carbide_composite", 100, "standard",
        std_electronics(notes="Medium Tactical Ultra-Scanner; Distortion Jammer; Decoy; ESM"),
        "1S", "g3rR2Wi",
        std_logistics(5.5, 0.7, 20000, "$10M", hyper=1, jumps=1, sig_cost=5),
        ["double_dr_vs_plasma", "double_dr_vs_shaped_charge", "ejection_seat"],
        {},
        [wpn_mount("imperial_fighter_blaster", "fixed_front", 2, "front", "Two linked blasters. Total ROF 6 (+1)."),
         wpn_mount("100mm_plasma_lance_missile", "wing_left", 1, "front", "6 light missiles."),
         wpn_mount("100mm_plasma_missile", "wing_right", 1, "front", "6 light missiles.")],
        description="The Empire's fastest interceptor. Next-Gen Syntech engines. Afterburner is always High-G.",
        source_url="https://psi-wars.wikidot.com/tempest-class-interceptor"
    ))

    ships.append(make_ship(
        "valiant_pattern_fighter_v1", "Valiant Pattern Fighter", "empire", 5, "fighter",
        105, "12", 4, 4, 12, 275, 30,
        std_afterburner(15, 350, range_override=6000),
        15, 15, 15, 15, 15, 15, None, 200, "standard",
        std_electronics(notes="Medium Tactical Ultra-Scanner; Distortion Jammer; Decoy; ESM"),
        "1SV+1xr", "g3rR2Wi",
        std_logistics(13.4, 3.0, 24000, "$7.5M", hyper=1, jumps=2, sig_cost=5),
        ["variable_geometry_wings"],
        {"Speed Geometry": {"top_speed": 550, "hnd": 3, "stall_speed": 65}},
        [wpn_mount("arc_gatling_blaster", "fixed_front", 2, "front", "Two linked ARC gatling blasters. Total ROF 24 (+4)."),
         wpn_mount("160mm_plasma_lance_missile", "wing_left", 1, "front", "8 missiles."),
         wpn_mount("160mm_plasma_missile", "wing_right", 1, "front", "8 missiles."),
         wpn_mount("400mm_isomeric_torpedo", "fixed_front", 1, "front", "Single torpedo.")],
        description="ARC-designed multirole fighter with variable geometry wings. Agility vs Speed configurations.",
        source_url="https://psi-wars.wikidot.com/valiant-pattern-fighter"
    ))

    ships.append(make_ship(
        "valkyrie_pattern_fighter_v1", "Valkyrie Pattern Fighter", "empire", 4, "fighter",
        90, "12", 5, 3, 15, 600, 50,
        std_afterburner(22, 700, range_override=4500),
        75, 75, 75, 75, 75, 75, "diamondoid", 300, "standard",
        std_electronics(notes="Medium Tactical Ultra-Scanner; Distortion Jammer; Decoy; ESM; Psychotronic Modules"),
        "1SV", "g3rRWi",
        std_logistics(7.0, 1.1, 18000, "$15M", sig_cost=10),
        ["psionic_amplifier", "psychotronic_modules"],
        {"With Hypersled": {"st_hp": 115, "hnd": 3, "accel": 8, "top_speed": 350, "stall_speed": 80}},
        [wpn_mount("arc_gatling_blaster", "fixed_front", 2, "front", "Two linked ARC gatling blasters. Total ROF 24 (+4)."),
         wpn_mount("lightning_cannon", "fixed_front", 1, "front", "Relic weapon. ROF 1/30. Psionic targeting.")],
        description="The premier Maradonian psionic fighter. Psychotronic modules amplify pilot abilities. Optional Hypersled adds mass and hyperspace capability.",
        source_url="https://psi-wars.wikidot.com/valkyrie-pattern-fighter"
    ))

    ships.append(make_ship(
        "vespa_class_interceptor_v1", "Vespa-Class Interceptor", "trader", 4, "interceptor",
        95, "12", 4, 3, 15, 450, 0,
        None,
        10, 10, 10, 10, 10, 10, "nanopolymer", 150, "standard",
        std_electronics(neural=False, notes="Medium Tactical Ultra-Scanner; Targeting +5; Distortion Jammer; Tactical ESM; Hyperspectral Sensors +3 notice"),
        "1SV", "G2Wi4RL",
        std_logistics(6.9, 0.4, 22000, "$6M", sig_cost=5),
        ["vtol", "configurable_wings"],
        {"High Maneuverability": {"hnd": 5, "accel": 3, "top_speed": 250}},
        [wpn_mount("fighter_blaster_cannon", "fixed_front", 2, "front", "Two linked blaster cannons. Total ROF 16 (+3)."),
         wpn_mount("particle_cannon_stinger", "fixed_front", 1, "front", "Underslung stinger. ROF 1/3.")],
        description="Export variant of the Hornet. Standard controls instead of neural interface. No Trader tech penalty.",
        source_url="https://psi-wars.wikidot.com/vespa-class-interceptor"
    ))

    ships.append(make_ship(
        "hammerhead_class_striker_v1", "Hammerhead Class Striker", "rath", 4, "striker",
        105, "8x", 0, 3, 15, 400, 75,
        std_afterburner(20, 500, hnd_mod=1, range_override=4500),
        500, 100, 100, 100, 100, 500, "nanopolymer", 0, "none",
        obsolete_electronics(notes="Obsolete Ultra-Scanner; Obsolete Targeting +4; Obsolete Distortion Jammer -2; Tactical ESM"),
        "1SV", "g2Wi3rR",
        std_logistics(10.0, 0.6, 18000, "$2M"),
        ["double_dr_vs_plasma", "explosive", "obsolete_electronics", "ramming_prow"],
        {},
        [wpn_mount("quad_repeater_cannon", "turret", 1, "all", "Turret-mounted quad repeater."),
         wpn_mount("internal_torpedo_400mm", "fixed_front", 1, "front", "Internal single-use torpedo."),
         wpn_mount("ramming_prow", "fixed_front", 1, "front", "Reinforced ramming prow.")],
        description="A heavily armored Rath suicide striker. DR 500 front/bottom, 100 elsewhere. HT 8x (explosive). Designed to ram targets.",
        tags=["rath", "striker"],
        source_url="https://psi-wars.wikidot.com/hammerhead-class-striker"
    ))

    # --- SM+5-6 SHIPS ---

    ships.append(make_ship(
        "grappler_class_assault_boat_v1", "Grappler Class Assault Boat", "redjack", 5, "striker",
        120, "12", 1, 4, 6, 350, 0,
        std_afterburner(10, 425, hnd_mod=1, range_override=4250),
        100, 50, 50, 50, 50, 50, "nanopolymer", 0, "none",
        std_electronics(ecm=-4, decoy=True, esm=True,
                        notes="Redjack Assault Boat electronics. Medium Tactical Ultra-Scanner; Targeting +5; Distortion Jammer; Decoy; ESM"),
        "1SV+6SV", "g2Wi3rR",
        std_logistics(19.3, 6.9, 17000, "$4.5M", sig_cost=5),
        ["double_dr_vs_plasma", "double_dr_vs_shaped_charge", "vtol", "boarding_craft"],
        {},
        [wpn_mount("sc4tr_plasma_gatling", "turret", 2, "all", "Two turret-mounted plasma gatlings.")],
        description="A Redjack boarding craft. Carries 6 combat passengers. VTOL capable.",
        tags=["redjack", "striker", "boarding"],
        source_url="https://psi-wars.wikidot.com/grappler-class-assault-boat"
    ))

    ships.append(make_ship(
        "raptor_pattern_striker_v1", "Raptor Pattern Striker", "empire", 6, "striker",
        130, "12", 2, 4, 6, 350, 25,
        std_afterburner(9, 400, range_override=8500),
        100, 50, 50, 50, 50, 50, "carbide_composite", 300, "standard",
        std_electronics(notes="Medium Tactical Ultra-Scanner; Targeting +5; Distortion Jammer; Decoy; ESM"),
        "1SV+1xr", "g3rR2Wi",
        std_logistics(27.0, 6.9, 34000, "$10M", hyper=1, jumps=2, sig_cost=10),
        ["double_dr_vs_plasma", "double_dr_vs_shaped_charge"],
        {},
        [wpn_mount("arc_gatling_blaster", "fixed_front", 2, "front", "Two linked ARC gatling blasters. Total ROF 24."),
         wpn_mount("160mm_plasma_lance_missile", "wing_left", 1, "front", "6 missiles."),
         wpn_mount("160mm_plasma_missile", "wing_right", 1, "front", "6 missiles."),
         wpn_mount("400mm_isomeric_torpedo", "fixed_front", 1, "front", "3 torpedoes.")],
        description="The Raptor is the standard Maradonian heavy strike fighter. Heavier than the Valiant with force screens and torpedoes.",
        source_url="https://psi-wars.wikidot.com/raptor-pattern-striker"
    ))

    ships.append(make_ship(
        "fugitive_class_escape_craft_v1", "Fugitive-Class Escape Craft", "rath", 6, "shuttle",
        150, "9f", 1, 4, 5, 150, 0,
        None,
        500, 500, 500, 500, 500, 500, None, 0, "none",
        obsolete_electronics(notes="Obsolete Ultra-Scanner; Obsolete Targeting +4; Obsolete Distortion Jammer -2; Obsolete Radio; Tactical ESM; Lithian security traps"),
        "6ASV", "G",
        std_logistics(36.0, 3.7, None, "$3.5M", hyper=1, jumps=3, endurance="1 month fuel"),
        ["obsolete_electronics", "vtol", "luxury_accommodation"],
        {},
        [wpn_mount("quad_repeater_cannon", "turret", 1, "all", "Single turret-mounted quad repeater.")],
        description="A Slaver escape craft with one luxury accommodation, 5 servant bunks, and thick armor. Rarely seen in spaceports.",
        tags=["rath", "shuttle", "escape_craft"],
        source_url="https://psi-wars.wikidot.com/wiki:fugitive-class-escape-craft"
    ))

    ships.append(make_ship(
        "high_roller_class_yacht_v1", "High Roller-Class Yacht", "empire", 6, "yacht",
        175, "11f", 2, 4, 5, 400, 0,
        None,
        500, 500, 500, 500, 500, 500, None, 300, "standard",
        std_electronics(notes="Medium Tactical Ultra-Scanner; Targeting +5; Distortion Jammer; Decoy; ESM"),
        "5ASV", "g3rR2Wi",
        std_logistics(50.0, 8.8, None, "$35M", hyper=2, jumps=3, endurance="1 month",
                      sig_cost=10),
        ["luxury_vessel", "vtol"],
        {},
        [wpn_mount("fighter_cannon_generic", "turret", 2, "all", "Two linked turret fighter cannons."),
         wpn_mount("400mm_isomeric_torpedo", "fixed_front", 1, "front", "4 torpedoes.")],
        description="A luxury yacht with surprisingly capable armament and thick armor.",
        tags=["empire", "yacht", "luxury"],
        source_url="https://psi-wars.wikidot.com/high-roller-class-yacht"
    ))

    ships.append(make_ship(
        "prestige_pattern_shuttle_v1", "Prestige-Pattern Diplomatic Shuttle", "empire", 7, "shuttle",
        200, "13", 0, 4, 2, 200, 0,
        None,
        200, 200, 200, 200, 200, 200, None, 300, "standard",
        std_electronics(notes="Medium Tactical Ultra-Scanner; Targeting +5; Distortion Jammer; Tactical ESM; Diplomatic comm suite"),
        "2+2ASV+12SV", "g3rR2Wi",
        std_logistics(80.0, 30.0, None, "$20M", hyper=2, jumps=5, endurance="1 month",
                      sig_cost=5),
        ["vtol", "diplomatic_vessel"],
        {},
        [wpn_mount("anti_personnel_blaster", "turret", 4, "all", "4 linked anti-personnel blaster turrets. Total ROF 12.")],
        description="Standard Imperial diplomatic and VIP transport shuttle. Carries up to 12 passengers in comfort.",
        tags=["empire", "shuttle", "diplomatic"],
        source_url="https://psi-wars.wikidot.com/prestige-pattern-diplomatic-shuttle"
    ))

    # --- CORVETTES (SM 7-8) ---

    ships.append(make_ship(
        "gypsy_moth_class_blockade_runner_v1", "Gypsy Moth-Class Blockade Runner", "trader", 6, "corvette",
        220, "13", 3, 4, 3, 300, 30,
        None,
        50, 50, 50, 50, 50, 50, "nanopolymer", 500, "standard",
        std_electronics(neural=True, notes="Medium Tactical Ultra-Scanner; Targeting +5; Distortion Jammer; Tactical ESM; Neural Interface; Tactical Computers +2 Tactics"),
        "9ASV", "2Wi4RL",
        std_logistics(90.0, 40.0, None, "$90M", hyper=2, jumps=None, endurance="Energy bank",
                      sig_cost=10),
        ["responsive_structure", "vtol", "configurable_wings", "trader_tech_penalty", "neural_interface_required"],
        {"High Maneuverability": {"hnd": 4, "accel": 3, "top_speed": 150}},
        [wpn_mount("muonic_fighter_cannon", "fixed_front", 2, "front", "Two linked muonic cannons.")],
        description="A Trader blockade runner with responsive structure and configurable wings. Neural interface required.",
        tags=["trader", "corvette", "blockade_runner"],
        source_url="https://psi-wars.wikidot.com/gypsy-moth-class-blockade-runner"
    ))

    ships.append(make_ship(
        "nomad_class_modular_corvette_v1", "Nomad-Class Modular Corvette", "redjack", 7, "corvette",
        225, "13", 1, 5, 7, 300, 0,
        None,
        150, 75, 75, 75, 75, 75, "nanopolymer", 500, "standard",
        redjack_corvette_electronics(),
        "4ASV", "g2t3rR",
        std_logistics(125.0, 25.0, None, "$25M", hyper=3, jumps=10, endurance="60 days",
                      sig_cost=10),
        ["double_dr_vs_plasma", "vtol", "modular"],
        {},
        [],
        module_slots=[
            {"slot_id": "turret_1", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Modular combat turret with 360 degree rotation."},
            {"slot_id": "turret_2", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Modular combat turret with 360 degree rotation."},
            {"slot_id": "engine", "slot_type": "engine", "weight_class": "any", "max_weight": None,
             "notes": "Modular engine including hyperdrive."},
            {"slot_id": "electronics", "slot_type": "electronics", "weight_class": "any", "max_weight": None,
             "notes": "Modular electronics lab."},
            {"slot_id": "cargo", "slot_type": "cargo", "weight_class": "any", "max_weight": None,
             "notes": "Modular hold: passenger accommodations or cargo."},
            {"slot_id": "armor", "slot_type": "armor", "weight_class": "any", "max_weight": None,
             "notes": "Modular armor overlay."},
        ],
        description="The most modular corvette in the galaxy. Everything can be swapped.",
        tags=["redjack", "corvette", "modular"],
        source_url="https://psi-wars.wikidot.com/nomad-class-modular-corvette"
    ))

    ships.append(make_ship(
        "scarab_class_defense_frigate_v1", "Scarab-Class Defense Frigate", "trader", 8, "frigate",
        400, "13", 2, 5, 1, 250, 0,
        None,
        500, 200, 500, 500, 200, 200, "nanopolymer", 1000, "standard",
        std_electronics(ecm=-4, scanner=150, ftl=30, comm=10000,
                        notes="Ultrascanner Open Mount 150mi; Targeting +5; Distortion Jammer; Tactical ESM; FTL Comm 30 parsec"),
        "9ASV", "2rR",
        std_logistics(600.0, 75.0, None, "$350M", hyper=2, jumps=None),
        ["double_dr_vs_plasma", "vtol"],
        {},
        [wpn_mount("corvette_muonic_cannon", "turret", 2, "all", "Two linked corvette-scale muonic turrets.")],
        description="A Trader defense frigate. Higher DR on front and sides (500), lower on top/bottom/rear (200). Force screen 1000.",
        tags=["trader", "frigate", "defense"],
        source_url="https://psi-wars.wikidot.com/scarab-class-defense-frigate"
    ))

    ships.append(make_ship(
        "skirmisher_class_corvette_v1", "Skirmisher-Class Corvette", "rath", 8, "corvette",
        500, "9f", 0, 4, 10, 75, 0,
        None,
        500, 250, 250, 250, 250, 250, None, 0, "none",
        obsolete_electronics(notes="Obsolete electronics suite. ECM -2."),
        "8ASV", "g2t",
        std_logistics(1300.0, 45.0, None, "$80M", hyper=1, jumps=3),
        ["fragile", "vtol"],
        {},
        [wpn_mount("quad_repeater_cannon", "turret", 2, "all", "Two turret-mounted quad repeaters."),
         wpn_mount("isomeric_heavy_torpedo", "fixed_front", 1, "front", "4 heavy torpedoes.")],
        description="A Rath corvette. Fragile but fast for its size, with heavy torpedo armament.",
        tags=["rath", "corvette"],
        source_url="https://psi-wars.wikidot.com/skirmisher-class-corvette"
    ))

    ships.append(make_ship(
        "tigershark_assault_corvette_v1", "Tigershark Assault Corvette", "redjack", 8, "corvette",
        400, "14", 1, 5, 6, 250, 0,
        None,
        1000, 400, 400, 400, 400, 400, "nanopolymer", 750, "standard",
        redjack_corvette_electronics(),
        "15ASV", "g6t4rR",
        std_logistics(600.0, 140.0, 200000, "$130M", hyper=2, jumps=7, endurance="30 days",
                      sig_cost=15),
        ["double_dr_vs_plasma", "vtol", "hardpoints"],
        {},
        [wpn_mount("corvette_scale_cannon", "turret", 1, "front", "Forward corvette-scale turret, 2 cannons (total ROF 2)."),
         wpn_mount("tractor_beam_st160", "rear_turret", 1, "rear", "Rear-mounted ST 160 tractor beam.")],
        module_slots=[
            {"slot_id": "fighter_turret_1", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Fighter-scale modular turret. Full rotation."},
            {"slot_id": "fighter_turret_2", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Fighter-scale modular turret. Full rotation."},
            {"slot_id": "fighter_turret_3", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Fighter-scale modular turret. Full rotation."},
            {"slot_id": "fighter_turret_4", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Fighter-scale modular turret. Full rotation."},
            {"slot_id": "hardpoint_left", "slot_type": "hardpoint", "weight_class": "any", "max_weight": 40000.0,
             "notes": "Rear hardpoint. Grappler assault boat, cargo pod, fuel pod, or engine pod."},
            {"slot_id": "hardpoint_right", "slot_type": "hardpoint", "weight_class": "any", "max_weight": 40000.0,
             "notes": "Rear hardpoint. Grappler assault boat, cargo pod, fuel pod, or engine pod."},
        ],
        description="A Redjack raiding corvette with modular turrets and rear hardpoints for Grappler assault boats.",
        tags=["redjack", "corvette", "raider"],
        source_url="https://psi-wars.wikidot.com/tigershark-class-assault-corvette"
    ))

    ships.append(make_ship(
        "toad_class_heavy_corvette_v1", "Toad-Class Heavy Corvette", "rath", 9, "corvette",
        1600, "9f", 0, 4, 10, 80, 0,
        None,
        1000, 500, 500, 500, 500, 500, None, 0, "none",
        obsolete_electronics(notes="Obsolete electronics. ECM -2."),
        "70ASV", "g2t",
        std_logistics(4250.0, 600.0, None, "$500M", hyper=1, jumps=7, endurance="3 months"),
        ["fragile", "vtol", "self_destruct"],
        {},
        [wpn_mount("quad_repeater_cannon", "turret", 4, "all", "4 turret-mounted quad repeaters."),
         wpn_mount("corvette_scale_cannon", "turret", 1, "all", "1 corvette-scale cannon turret."),
         wpn_mount("isomeric_torpedo_bay_single", "fixed_front", 1, "front", "Torpedo bay, 4 torpedoes.")],
        description="A massive Rath heavy corvette. Fragile but heavily armed. Nuclear self-destruct device.",
        tags=["rath", "corvette", "heavy"],
        source_url="https://psi-wars.wikidot.com/toad-class-heavy-corvette"
    ))

    ships.append(make_ship(
        "wrangler_class_corvette_v1", "Wrangler-Class Corvette", "redjack", 7, "corvette",
        280, "14", 0, 5, 2, 150, 0,
        None,
        500, 500, 500, 500, 500, 500, "nanopolymer", 250, "standard",
        redjack_corvette_electronics(),
        "4ASV", "G4t4rL",
        std_logistics(250.0, 66.0, 200000, "$45M", hyper=2, jumps=7, endurance="30 days"),
        ["double_dr_vs_plasma", "vtol"],
        {},
        [],
        module_slots=[
            {"slot_id": "turret_1", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Modular turret."},
            {"slot_id": "turret_2", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Modular turret."},
            {"slot_id": "turret_3", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Modular turret."},
            {"slot_id": "turret_4", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0,
             "notes": "Modular turret."},
        ],
        description="A Redjack utility corvette with 4 modular weapon turrets.",
        tags=["redjack", "corvette", "utility"],
        source_url="https://psi-wars.wikidot.com/wrangler-class-corvette"
    ))

    # --- FRIGATES / ASSAULT CARRIERS (SM 9) ---

    ships.append(make_ship(
        "lancer_pattern_assault_frigate_v1", "Lancer-Pattern Assault Frigate", "empire", 9, "frigate",
        700, "12", 0, 5, 2, 250, 0,
        None,
        2500, 500, 500, 500, 500, 500, "carbide_composite", 1000, "standard",
        std_electronics(ecm=-4, scanner=150, ftl=30, comm=10000,
                        notes="Tactical Ultra-Scanner 150mi; Targeting +5; Distortion Jammer; Area Jammer; Scrambler"),
        "90ASV", "g3rR2t",
        std_logistics(2750.0, 285.0, None, "$750M", hyper=2, jumps=4),
        ["double_dr_vs_plasma", "vtol"],
        {},
        [wpn_mount("disruptor_cannon", "turret", 1, "all", "Disruptor cannon turret. Surge damage."),
         wpn_mount("corvette_scale_cannon", "turret", 2, "all", "2 corvette-scale cannon turrets (Total ROF 6).")],
        description="An Imperial assault frigate with a disruptor cannon for disabling targets. DR 2500 front, 500 elsewhere.",
        tags=["empire", "frigate", "assault"],
        source_url="https://psi-wars.wikidot.com/lancer-pattern-assault-frigate"
    ))

    ships.append(make_ship(
        "raider_class_assault_carrier_v1", "Raider-Class Assault Carrier", "redjack", 9, "carrier",
        800, "14", 0, 5, 12, 125, 0,
        None,
        2000, 400, 400, 400, 400, 400, "nanopolymer", 750, "standard",
        redjack_corvette_electronics(notes="Ultrascanner Open Mount 150mi; Targeting +5; Distortion Jammer; Large FTL 30pc; Area Jammer"),
        "80ASV", "g6t4rR",
        std_logistics(4500.0, 600.0, None, "$2B", hyper=2, jumps=7, endurance="30 days",
                      sig_cost=20),
        ["double_dr_vs_plasma", "vtol"],
        {},
        [wpn_mount("corvette_scale_cannon", "turret", 4, "all", "4 corvette-scale cannon turrets."),
         wpn_mount("plasma_flak_turret", "turret", 4, "all", "4 plasma flak turrets.")],
        module_slots=[
            {"slot_id": "fighter_turret_1", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0, "notes": "Modular fighter turret."},
            {"slot_id": "fighter_turret_2", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0, "notes": "Modular fighter turret."},
            {"slot_id": "fighter_turret_3", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0, "notes": "Modular fighter turret."},
            {"slot_id": "fighter_turret_4", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0, "notes": "Modular fighter turret."},
        ],
        description="A Redjack assault carrier. Carries fighters and has modular fighter-scale turrets.",
        tags=["redjack", "carrier", "assault"],
        source_url="https://psi-wars.wikidot.com/raider-class-assault-carrier"
    ))

    # --- CRUISERS (SM 11-12) ---

    ships.append(make_ship(
        "kodiak_class_light_cruiser_v1", "Kodiak-Class Light Cruiser", "redjack", 11, "cruiser",
        3000, "14", 0, 6, 10, 150, 0,
        None,
        2000, 2000, 2000, 2000, 2000, 2000, "nanopolymer", 2000, "standard",
        capital_electronics(notes="Capital-Scale Ultra-Scanner 4000mi; Targeting +5; Area Jammer; Scrambler; FTL Comm 30pc"),
        "200ASV", "gG10t4rL",
        std_logistics(27000.0, 3750.0, None, "$6B", hyper=3, jumps=7),
        ["double_dr_vs_plasma", "vtol"],
        {},
        [wpn_mount("corvette_scale_cannon", "turret", 10, "all", "10 corvette-scale cannon turrets."),
         wpn_mount("plasma_flak_turret", "turret", 4, "all", "4 plasma flak turrets.")],
        module_slots=[
            {"slot_id": "fighter_turret_1", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0, "notes": "Modular fighter turret."},
            {"slot_id": "fighter_turret_2", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0, "notes": "Modular fighter turret."},
            {"slot_id": "fighter_turret_3", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0, "notes": "Modular fighter turret."},
            {"slot_id": "fighter_turret_4", "slot_type": "weapon", "weight_class": "any", "max_weight": 4000.0, "notes": "Modular fighter turret."},
        ],
        description="A Redjack light cruiser. Heavily armed with corvette-scale weapons and modular turrets.",
        tags=["redjack", "cruiser"],
        source_url="https://psi-wars.wikidot.com/kodiak-class-light-cruiser"
    ))

    ships.append(make_ship(
        "regal_pattern_cruiser_v1", "Regal-Pattern Cruiser", "empire", 11, "cruiser",
        3500, "13", -1, 6, 6, 110, 0,
        None,
        2500, 2500, 2500, 2500, 2500, 2500, "carbide_composite", 4000, "standard",
        capital_electronics(notes="Capital-Scale Ultra-Scanner; Targeting +5; Area Jammer; Scrambler; FTL Comm 300pc"),
        "450ASV", "Gs17t",
        std_logistics(40000.0, 6000.0, None, "$10B", hyper=2, jumps=5),
        ["double_dr_vs_plasma", "vtol"],
        {},
        [wpn_mount("capital_scale_cannon", "turret", 4, "all", "4 capital-scale cannon turrets (Total ROF 8)."),
         wpn_mount("corvette_scale_cannon", "turret", 6, "all", "6 corvette-scale turrets (Total ROF 18)."),
         wpn_mount("plasma_flak_turret", "turret", 6, "all", "6 plasma flak turrets.")],
        description="The standard Maradonian heavy cruiser. Backbone of the Imperial fleet.",
        tags=["empire", "cruiser"],
        source_url="https://psi-wars.wikidot.com/regal-pattern-cruiser"
    ))

    ships.append(make_ship(
        "dominion_class_heavy_cruiser_v1", "Dominion-Class Heavy Cruiser", "empire", 12, "cruiser",
        5000, "12", -2, 6, 5, 100, 0,
        None,
        3000, 3000, 3000, 3000, 3000, 3000, None, 5000, "heavy",
        capital_electronics(),
        "1200ASV", "gGs20t",
        std_logistics(150000.0, 13000.0, None, "$30B", hyper=2, jumps=5),
        ["heavy_force_screen", "capital_ship"],
        {},
        [wpn_mount("capital_scale_cannon", "turret", 8, "all", "8 capital-scale turrets (Total ROF 16)."),
         wpn_mount("corvette_scale_cannon", "turret", 6, "all", "6 corvette-scale turrets."),
         wpn_mount("plasma_flak_turret", "turret", 6, "all", "6 plasma flak turrets.")],
        description="An Imperial heavy cruiser with heavy force screens that ignore all armor divisors.",
        tags=["empire", "cruiser", "heavy"],
        source_url="https://psi-wars.wikidot.com/dominion-class-heavy-cruiser"
    ))

    # --- BATTLESHIPS / CARRIERS (SM 12-14) ---

    ships.append(make_ship(
        "executioner_class_artillery_cruiser_v1", "Executioner-Class Artillery Cruiser", "empire", 13, "cruiser",
        7000, "12", -5, 6, 1, 50, 0,
        None,
        4000, 2500, 2500, 2500, 2500, 2500, None, 7500, "heavy",
        capital_electronics(),
        "2000ASV", "gGs4t",
        std_logistics(370000.0, 20000.0, None, "$80B", hyper=2, jumps=3),
        ["heavy_force_screen", "capital_ship"],
        {},
        [wpn_mount("pulsar_super_cannon", "fixed_front", 1, "front", "Pulsar Super-Cannon. ROF 1/10. Extreme range."),
         wpn_mount("super_heavy_cannon", "turret", 2, "all", "2 super-heavy turrets (Total ROF 6)."),
         wpn_mount("plasma_flak_turret", "turret", 4, "all", "4 plasma flak turrets.")],
        description="An Imperial artillery cruiser with a devastating Pulsar Super-Cannon. Designed for bombardment from extreme range.",
        tags=["empire", "cruiser", "artillery"],
        source_url="https://psi-wars.wikidot.com/executioner-class-artillery-cruiser"
    ))

    ships.append(make_ship(
        "mauler_class_battlecarrier_v1", "Mauler-Class Battle-Carrier", "rath", 12, "battleship",
        5000, "9f", -4, 5, 2, 50, 0,
        None,
        6000, 2500, 2500, 2500, 2500, 2500, None, 0, "none",
        capital_electronics(ecm=-4, notes="Capital electronics. Nuclear self-destruct."),
        "1200ASV", "gG10t",
        std_logistics(110000.0, 30000.0, None, "$10B", hyper=1, jumps=7),
        ["fragile", "capital_ship", "nuclear_self_destruct"],
        {},
        [wpn_mount("capital_scale_cannon", "turret", 4, "all", "4 capital turrets."),
         wpn_mount("corvette_scale_cannon", "turret", 6, "all", "6 corvette turrets."),
         wpn_mount("mauler_beam", "fixed_front", 2, "front", "2 short-range Mauler Beams."),
         wpn_mount("guillotine_weapon", "fixed_front", 1, "front", "Guillotine close-range weapon.")],
        description="A Rath battle-carrier. Fragile but massively armed. Carries fighters. Nuclear self-destruct.",
        tags=["rath", "battleship", "carrier"],
        source_url="https://psi-wars.wikidot.com/mauler-class-battle-carrier"
    ))

    ships.append(make_ship(
        "arcana_pattern_carrier_v1", "Arcana-Pattern Carrier", "empire", 13, "carrier",
        6000, "13", -5, 6, 1, 50, 0,
        None,
        2500, 2500, 2500, 2500, 2500, 2500, "carbide_composite", 10000, "heavy",
        capital_electronics(),
        "7100ASV", "gGs22t",
        std_logistics(340000.0, 150000.0, None, "$60B", hyper=2, jumps=5),
        ["double_dr_vs_plasma", "heavy_force_screen", "capital_ship"],
        {},
        [wpn_mount("capital_scale_cannon", "turret", 6, "all", "6 capital turrets."),
         wpn_mount("corvette_scale_cannon", "turret", 8, "all", "8 corvette turrets."),
         wpn_mount("plasma_flak_turret", "turret", 8, "all", "8 plasma flak turrets.")],
        description="The primary Imperial fleet carrier. Massive hangar capacity.",
        tags=["empire", "carrier", "capital_ship"],
        source_url="https://psi-wars.wikidot.com/arcana-pattern-carrier"
    ))

    ships.append(make_ship(
        "legion_class_super_carrier_v1", "Legion-Class Super Carrier", "empire", 14, "carrier",
        8000, "12", -5, 6, 1, 50, 0,
        None,
        3000, 3000, 3000, 3000, 3000, 3000, None, 10000, "heavy",
        capital_electronics(),
        "75000ASV", "gGs16t",
        std_logistics(1200000.0, 620000.0, None, "$90B", hyper=2, jumps=5),
        ["heavy_force_screen", "capital_ship"],
        {},
        [wpn_mount("capital_scale_cannon", "turret", 6, "all", "6 capital turrets."),
         wpn_mount("plasma_flak_turret", "turret", 8, "all", "8 plasma flak turrets.")],
        description="The largest Imperial carrier. Houses tens of thousands of crew and hundreds of fighters.",
        tags=["empire", "carrier", "super_carrier"],
        source_url="https://psi-wars.wikidot.com/legion-class-super-carrier"
    ))

    ships.append(make_ship(
        "imperator_class_dreadnought_v1", "Imperator-Class Dreadnought", "empire", 14, "dreadnought",
        9000, "12", -4, 6, 1, 75, 0,
        None,
        5000, 3000, 3000, 3000, 3000, 3000, None, 15000, "heavy",
        capital_electronics(),
        "8500ASV", "gGs40t",
        std_logistics(850000.0, 100000.0, None, "$190B", hyper=2, jumps=5,
                      endurance="50-year fusion reactor", sig_cost=30),
        ["heavy_force_screen", "capital_ship"],
        {},
        [wpn_mount("super_heavy_cannon", "turret", 4, "all", "4 super-heavy turrets (Total ROF 12)."),
         wpn_mount("capital_scale_cannon", "turret", 12, "all", "12 capital turrets (Total ROF 24)."),
         wpn_mount("plasma_flak_turret", "turret", 8, "all", "8 plasma flak turrets (4 front, 4 rear)."),
         wpn_mount("tractor_beam_st1000", "turret", 2, "all", "2 ST 1000 tractor beams.")],
        description="The most iconic vessel of the Imperial fleet. A looming behemoth of firepower.",
        tags=["empire", "dreadnought", "capital_ship"],
        source_url="https://psi-wars.wikidot.com/imperator-class-dreadnought"
    ))

    ships.append(make_ship(
        "spire_class_mobile_fortress_v1", "Spire-Class Mobile Fortress", "rath", 11, "battleship",
        3000, "9f", -4, 5, 1, 25, 0,
        None,
        5000, 3000, 3000, 3000, 3000, 3000, None, 0, "none",
        capital_electronics(ecm=-4, notes="Capital electronics. Nuclear self-destruct."),
        "2500ASV", "gG13t",
        std_logistics(30000.0, 15000.0, None, "$3.5B", hyper=1, jumps=3),
        ["fragile", "capital_ship", "nuclear_self_destruct"],
        {},
        [wpn_mount("spire_plasma_cannon", "turret", 1, "all", "Spire-scale plasma cannon. ROF 1/10."),
         wpn_mount("corvette_scale_cannon", "turret", 4, "all", "4 corvette turrets."),
         wpn_mount("quad_repeater_cannon", "turret", 6, "all", "6 quad repeater turrets."),
         wpn_mount("isomeric_heavy_torpedo", "fixed_front", 1, "front", "1 heavy torpedo.")],
        description="A Rath mobile fortress. Fragile but bristling with weapons. Nuclear self-destruct.",
        tags=["rath", "battleship", "fortress"],
        source_url="https://psi-wars.wikidot.com/spire-class-mobile-fortress"
    ))

    # --- TRADER ARKS (SM 15-16) ---

    ships.append(make_ship(
        "trader_ark_v1", "Trader Ark", "trader", 16, "carrier",
        25000, "13", -5, 5, 1, 50, 0,
        None,
        5000, 5000, 5000, 5000, 5000, 5000, None, 10000, "heavy",
        capital_electronics(ecm=-4, scanner=4000, ftl=300,
                            notes="Capital Ultra-Scanner 4000mi; Targeting +5; Area Jammer; Scrambler; FTL Comm 300pc"),
        "1000000ASV", "12T6rT",
        std_logistics(15000000.0, 5000000.0, None, "$10T", hyper=1, jumps=None,
                      endurance="Fusion reactor"),
        ["heavy_force_screen", "capital_ship", "trader_tech_penalty"],
        {},
        [wpn_mount("trader_capital_cannon", "turret", 6, "all", "6 Trader capital-scale muonic turrets. Surge."),
         wpn_mount("plasma_flak_turret", "turret", 6, "all", "6 plasma flak turrets.")],
        description="A small Trader Ark. Larger arks have more HP and larger populations. Mobile cities in space.",
        tags=["trader", "carrier", "ark"],
        source_url="https://psi-wars.wikidot.com/trader-ark"
    ))

    ships.append(make_ship(
        "trader_ark_tender_v1", "Trader Ark Tender", "trader", 15, "battleship",
        15000, "13", -4, 5, 1, 150, 0,
        None,
        10000, 10000, 10000, 10000, 10000, 10000, None, 20000, "heavy",
        capital_electronics(ecm=-4, scanner=4000, ftl=300,
                            notes="Capital Ultra-Scanner; Targeting +5; Full electronic warfare suite; FTL Comm 300pc"),
        "10000ASV", "12T9rT",
        std_logistics(3000000.0, 900000.0, None, "$1.5T", hyper=1, jumps=None,
                      endurance="Fusion reactor"),
        ["heavy_force_screen", "capital_ship", "trader_tech_penalty"],
        {},
        [wpn_mount("spinal_pulsar", "fixed_front", 1, "front", "Spinal Pulsar. ROF 1/10."),
         wpn_mount("spinal_blaster", "fixed_front", 1, "front", "Spinal Blaster. ROF 1/10."),
         wpn_mount("spinal_muonic_blaster", "fixed_front", 1, "front", "Spinal Muonic Blaster. ROF 1/10. Surge."),
         wpn_mount("super_heavy_muonic_cannon", "turret", 4, "all", "4 super-heavy muonic turrets. Surge."),
         wpn_mount("capital_muonic_cannon", "turret", 8, "all", "8 capital muonic turrets. Surge."),
         wpn_mount("plasma_flak_turret", "turret", 8, "all", "8 plasma flak turrets.")],
        description="An Ark Tender at full original battleship capability. Immensely powerful. Trader tech penalty applies.",
        tags=["trader", "battleship", "ark_tender"],
        source_url="https://psi-wars.wikidot.com/trader-ark-tender"
    ))

    for ship in ships:
        tid = ship["template_id"]
        save_json(SHIPS_DIR, f"{tid}.json", ship)


if __name__ == "__main__":
    os.makedirs(WEAPONS_DIR, exist_ok=True)
    os.makedirs(MODULES_DIR, exist_ok=True)
    os.makedirs(SHIPS_DIR, exist_ok=True)

    generate_weapons()
    generate_ships()

    print("\n=== VALIDATION ===")
    import sys
    sys.path.insert(0, ".")
    from m3_data_vault.models.template import ShipTemplate
    from m3_data_vault.models.weapon import WeaponDefinition
    from m3_data_vault.models.module import ModuleDefinition

    errors = 0
    for wf in sorted(WEAPONS_DIR.glob("*.json")):
        if "invalid" in wf.stem:
            continue
        try:
            WeaponDefinition(**json.loads(wf.read_text()))
        except Exception as e:
            print(f"  WEAPON ERROR: {wf.name}: {e}")
            errors += 1

    for mf in sorted(MODULES_DIR.glob("*.json")):
        if "invalid" in mf.stem:
            continue
        try:
            ModuleDefinition(**json.loads(mf.read_text()))
        except Exception as e:
            print(f"  MODULE ERROR: {mf.name}: {e}")
            errors += 1

    for sf in sorted(SHIPS_DIR.glob("*.json")):
        if "invalid" in sf.stem:
            continue
        try:
            ShipTemplate(**json.loads(sf.read_text()))
        except Exception as e:
            print(f"  SHIP ERROR: {sf.name}: {e}")
            errors += 1

    wcount = len(list(WEAPONS_DIR.glob("*.json"))) - 1  # minus invalid
    mcount = len(list(MODULES_DIR.glob("*.json"))) - 1
    scount = len(list(SHIPS_DIR.glob("*.json"))) - 1

    print(f"\n  Weapons: {wcount} | Modules: {mcount} | Ships: {scount}")
    if errors == 0:
        print("  ALL VALID!")
    else:
        print(f"  {errors} ERRORS found!")
