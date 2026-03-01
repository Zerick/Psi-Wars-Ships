// components/WeaponsList.jsx
// Weapons list. Full stats shown on own card; name+type only on opponent card.

export default function WeaponsList({ weapons, showFull }) {
  if (!weapons || weapons.length === 0) return null;

  return (
    <div className="border-t border-slate-700 pt-2">
      <p className="text-xs text-slate-500 mb-1.5 uppercase tracking-wider">Weapons</p>
      <div className="space-y-1.5">
        {weapons.map((w) => (
          <WeaponRow key={w.weapon_id} weapon={w} showFull={showFull} />
        ))}
      </div>
    </div>
  );
}

function WeaponRow({ weapon, showFull }) {
  const typeColour = {
    gun: "text-amber-400",
    missile: "text-orange-400",
    torpedo: "text-red-400",
  }[weapon.weapon_type] || "text-slate-400";

  const mountLabel = weapon.mount_type === "turret" ? "T" : "F";

  return (
    <div className="text-xs">
      <div className="flex items-center gap-1.5 flex-wrap">
        <span
          className={`font-mono text-[10px] px-1 rounded border ${
            weapon.mount_type === "turret"
              ? "border-blue-700 text-blue-400"
              : "border-slate-600 text-slate-400"
          }`}
        >
          {mountLabel}
        </span>
        <span className={`font-semibold ${typeColour}`}>{weapon.name}</span>
        {weapon.is_disabled && (
          <span className="text-red-500 text-[10px] font-bold">DISABLED</span>
        )}
      </div>

      {showFull && (
        <div className="mt-0.5 ml-5 text-slate-400 space-x-2">
          <span>
            {weapon.damage_dice}d×{weapon.damage_mult}{" "}
            <span className="text-slate-500">{weapon.damage_type}</span>
          </span>
          {weapon.armor_divisor > 1 && (
            <span className="text-slate-500">÷{weapon.armor_divisor}</span>
          )}
          <span>Acc {weapon.accuracy}</span>
          <span>RoF {weapon.rof}</span>
          {weapon.shots_max > 0 && (
            <span>{weapon.shots_current}/{weapon.shots_max} shots</span>
          )}
          {weapon.is_linked === true && <span className="text-blue-400">Linked</span>}
          {weapon.is_light_turret === true && <span className="text-indigo-400">Light</span>}
        </div>
      )}
    </div>
  );
}
