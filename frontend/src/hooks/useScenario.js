// hooks/useScenario.js
// Scenario state management. Subscribes to WebSocket events from useWebSocket.
// Drop-in addition — does not modify useSession.js or useWebSocket.js.

import { useState, useEffect, useCallback } from "react";

const API = import.meta.env.VITE_API_URL || "";

export function useScenario({ sessionId, token, isGm, wsLastMessage }) {
  const [scenario, setScenario] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // -------------------------------------------------------------------------
  // Load scenario on mount
  // -------------------------------------------------------------------------
  const loadScenario = useCallback(async () => {
    if (!sessionId || !token) return;
    try {
      const res = await fetch(
        `${API}/sessions/${sessionId}/scenario?token=${token}`
      );
      if (res.ok) {
        const data = await res.json();
        setScenario(data); // may be null if no scenario yet
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [sessionId, token]);

  useEffect(() => {
    loadScenario();
  }, [loadScenario]);

  // -------------------------------------------------------------------------
  // Handle incoming WebSocket messages
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!wsLastMessage) return;
    let msg;
    try {
      msg = typeof wsLastMessage === "string" ? JSON.parse(wsLastMessage) : wsLastMessage;
    } catch {
      return;
    }

    switch (msg.type) {
      case "scenario_created":
        setScenario((prev) => ({
          ...msg.data,
          ships: prev?.ships || [],
        }));
        break;

      case "ship_added":
        setScenario((prev) => {
          if (!prev) return prev;
          const exists = prev.ships.some((s) => s.ship_id === msg.data.ship_id);
          return {
            ...prev,
            ships: exists
              ? prev.ships.map((s) =>
                  s.ship_id === msg.data.ship_id ? msg.data : s
                )
              : [...prev.ships, msg.data],
          };
        });
        break;

      case "ship_updated":
      case "ship_assigned":
        setScenario((prev) => {
          if (!prev) return prev;
          const updated = msg.type === "ship_assigned" ? msg.data.ship : msg.data;
          return {
            ...prev,
            ships: prev.ships.map((s) =>
              s.ship_id === updated.ship_id ? updated : s
            ),
          };
        });
        break;

      case "ship_removed":
        setScenario((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            ships: prev.ships.filter((s) => s.ship_id !== msg.data.ship_id),
          };
        });
        break;

      default:
        break;
    }
  }, [wsLastMessage]);

  // -------------------------------------------------------------------------
  // API actions
  // -------------------------------------------------------------------------
  const createScenario = useCallback(
    async (name) => {
      const res = await fetch(
        `${API}/scenarios?session_id=${sessionId}&token=${token}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        }
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    [sessionId, token]
  );

  const addShip = useCallback(
    async ({ library_key, ship }) => {
      const res = await fetch(
        `${API}/scenarios/${scenario?.scenario_id}/ships?session_id=${sessionId}&token=${token}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ library_key, ship }),
        }
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    [sessionId, token, scenario?.scenario_id]
  );

  const patchShip = useCallback(
    async (shipId, fields) => {
      const res = await fetch(
        `${API}/scenarios/${scenario?.scenario_id}/ships/${shipId}?session_id=${sessionId}&token=${token}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fields }),
        }
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    [sessionId, token, scenario?.scenario_id]
  );

  const patchPilot = useCallback(
    async (shipId, fields) => {
      const res = await fetch(
        `${API}/scenarios/${scenario?.scenario_id}/ships/${shipId}/pilot?session_id=${sessionId}&token=${token}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fields }),
        }
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    [sessionId, token, scenario?.scenario_id]
  );

  const patchSystem = useCallback(
    async (shipId, systemName, status) => {
      const res = await fetch(
        `${API}/scenarios/${scenario?.scenario_id}/ships/${shipId}/systems/${systemName}?session_id=${sessionId}&token=${token}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        }
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    [sessionId, token, scenario?.scenario_id]
  );

  const assignShip = useCallback(
    async (shipId, userId) => {
      const res = await fetch(
        `${API}/scenarios/${scenario?.scenario_id}/ships/${shipId}/assign?session_id=${sessionId}&token=${token}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: userId }),
        }
      );
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    [sessionId, token, scenario?.scenario_id]
  );

  const removeShip = useCallback(
    async (shipId) => {
      const res = await fetch(
        `${API}/scenarios/${scenario?.scenario_id}/ships/${shipId}?session_id=${sessionId}&token=${token}`,
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error(await res.text());
    },
    [sessionId, token, scenario?.scenario_id]
  );

  return {
    scenario,
    loading,
    error,
    createScenario,
    addShip,
    patchShip,
    patchPilot,
    patchSystem,
    assignShip,
    removeShip,
    reload: loadScenario,
  };
}
