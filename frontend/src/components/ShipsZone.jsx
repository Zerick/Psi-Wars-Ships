// components/ShipsZone.jsx
// Horizontal scrollable row of ship cards. Sits above the log feed in SessionView.
// Renders ShipCard (full) for own ships and GM, ShipCardOpponent (reduced) for others.

import ShipCard from "./ShipCard";
import ShipCardOpponent from "./ShipCardOpponent";

export default function ShipsZone({
  ships,
  myUserId,
  isGm,
  participants,
  onPatchShip,
  onPatchPilot,
  onPatchSystem,
  onRemoveShip,
  onAssignShip,
}) {
  if (!ships || ships.length === 0) return null;

  return (
    <div className="w-full overflow-x-auto pb-2">
      <div className="flex gap-3 min-w-max px-1">
        {ships.map((ship) => {
          const isOwn = ship.assigned_user_id === myUserId;
          const showFull = isGm || isOwn;
          const assignedPlayer = participants?.find(
            (p) => p.user_id === ship.assigned_user_id
          );

          if (showFull) {
            return (
              <ShipCard
                key={ship.ship_id}
                ship={ship}
                isGm={isGm}
                participants={participants}
                onPatchShip={onPatchShip}
                onPatchPilot={onPatchPilot}
                onPatchSystem={onPatchSystem}
                onRemoveShip={onRemoveShip}
                onAssignShip={onAssignShip}
              />
            );
          }

          return (
            <ShipCardOpponent
              key={ship.ship_id}
              ship={ship}
              assignedPlayerName={assignedPlayer?.display_name}
            />
          );
        })}
      </div>
    </div>
  );
}
