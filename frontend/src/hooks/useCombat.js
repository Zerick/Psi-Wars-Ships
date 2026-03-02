// hooks/useCombat.js
// Combat state management + combat log card injection.
// Cards are injected into logEntries (passed via callback) when WS events arrive.

import { useState, useEffect, useCallback } from "react";

const API = import.meta.env.VITE_API_URL || "";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function uid() {
  return Math.random().toString(36).slice(2)
}

// ---------------------------------------------------------------------------
export function useCombat({ sessionId, token, scenarioId, isGm, wsLastMessage, onInjectLog }) {
  const [combat, setCombat]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  // ------------------------------------------------------------------
  // Load initial combat state
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!scenarioId) { setLoading(false); return }
    let cancelled = false
    const load = async () => {
      try {
        const res = await fetch(`${API}/scenarios/${scenarioId}/combat?token=${token}`)
        if (!cancelled && res.ok) setCombat(await res.json())
      } catch(e) { if (!cancelled) setError(e.message) }
      finally    { if (!cancelled) setLoading(false) }
    }
    load()
    return () => { cancelled = true }
  }, [scenarioId, token])

  // ------------------------------------------------------------------
  // Inject a combat log card
  // ------------------------------------------------------------------
  const injectCard = useCallback((type, data) => {
    if (!onInjectLog) return
    onInjectLog({
      entry_id:   uid(),
      entry_type: type,
      data,
    })
  }, [onInjectLog])

  // ------------------------------------------------------------------
  // WebSocket event handler
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!wsLastMessage) return
    const { type, data } = wsLastMessage

    switch (type) {

      case 'combat_started':
        setCombat(data)
        injectCard('combat_phase', { round: data.current_round, phase: 'COMBAT BEGINS', description: '' })
        break

      case 'phase_changed': {
        setCombat(prev => prev ? { ...prev, current_phase: data.phase, current_round: data.round } : prev)
        const phaseLabels = {
          declaration: 'Declaration Phase — submit your maneuvers',
          chase:       'Chase Phase — roll your chase dice',
          action:      'Action Phase — ships act in initiative order',
          end_round:   'End of Round',
        }
        injectCard('combat_phase', {
          round: data.round,
          phase: (data.phase || '').toUpperCase().replace('_', ' '),
          description: phaseLabels[data.phase] || '',
        })
        break
      }

      case 'declarations_revealed':
        setCombat(prev => prev ? { ...prev, declarations: data.declarations } : prev)
        break

      case 'declaration_submitted':
        setCombat(prev => {
          if (!prev) return prev
          const decls = [...(prev.declarations || [])]
          const idx = decls.findIndex(d => d.ship_id === data.ship_id)
          if (idx >= 0) decls[idx] = { ...decls[idx], submitted: true }
          else decls.push({ ship_id: data.ship_id, submitted: true })
          return { ...prev, declarations: decls }
        })
        break

      case 'chase_roll_submitted':
        setCombat(prev => prev ? { ...prev } : prev)
        break

      case 'chase_card':
        // Inject or replace chase card in log (combat_card_id used for in-place update)
        injectCard('combat_chase', {
          combat_card_id: data.combat_card_id || `chase-${data.ship_id}`,
          ship_id:        data.ship_id,
          ship_name:      data.ship_name || data.ship_id?.slice(0, 8),
          maneuver:       data.maneuver || '',
          npc:            !!data.npc,
          rolled:         !!data.rolled,
          roll:           data.roll ?? null,
          bonus:          data.bonus ?? null,
          mos:            data.mos ?? null,
          owner_user_id:  data.owner_user_id || null,
          combat_id:      data.combat_id,
        })
        break

      case 'chase_resolved':
        setCombat(prev => {
          if (!prev) return prev
          return { ...prev, ranges: data.updated_ranges }
        })
        if (data.updated_ranges) {
          data.updated_ranges.forEach(r => {
            if (r.resolution) {
              injectCard('combat_chase_resolution', {
                winner:         r.resolution.winner_name,
                loser:          r.resolution.loser_name,
                victory_margin: r.resolution.victory_margin,
                new_range:      r.range_band,
                description:    r.resolution.description || '',
              })
            }
          })
        }
        break

      case 'action_submitted':
        if (data.attack_hit && data.dodge_roll == null) {
          injectCard('combat_dodge', {
            combat_card_id: `dodge-${data.action_id}`,
            action_id:      data.action_id,
            combat_id:      data.combat_id,
            ship_id:        data.target_ship_id,
            ship_name:      data.target_ship_name || 'Defender',
            attacker_name:  data.acting_ship_name || 'Attacker',
            dodge_bonus:    data.dodge_effective || 9,
            breakdown:      [{ label: 'Dodge', value: data.dodge_effective || 9 }],
            owner_user_id:  data.target_owner_user_id,
            npc:            !!data.target_is_npc,
            rolled:         false,
          })
        }
        break

      case 'defense_submitted':
        injectCard('combat_dodge', {
          combat_card_id: `dodge-${data.action_id}`,
          action_id:      data.action_id,
          combat_id:      data.combat_id,
          ship_id:        data.target_ship_id,
          ship_name:      data.target_ship_name || 'Defender',
          attacker_name:  data.acting_ship_name || 'Attacker',
          dodge_bonus:    data.dodge_effective || 9,
          breakdown:      [{ label: 'Dodge', value: data.dodge_effective || 9 }],
          owner_user_id:  data.target_owner_user_id,
          npc:            !!data.target_is_npc,
          roll:           data.dodge_roll,
          dodged:         data.dodge_success,
          rolled:         true,
        })
        break

      case 'damage_submitted':
        injectCard('combat_damage', {
          ship_name:     data.target_ship_name || 'Target',
          attacker_name: data.acting_ship_name || 'Attacker',
          damage_rolled: data.damage_rolled,
          damage_net:    data.damage_net,
          hp_before:     data.hp_before,
          hp_after:      data.hp_after,
          screen_before: data.screen_before,
          screen_after:  data.screen_after,
          description:   data.damage_description || '',
        })
        break

      case 'ship_acted':
        setCombat(prev => {
          if (!prev) return prev
          const order = (prev.initiative_order || []).map(s =>
            s.ship_id === data.ship_id ? { ...s, has_acted: true } : s
          )
          return { ...prev, initiative_order: order }
        })
        break

      case 'round_ended':
        setCombat(prev => prev ? { ...prev, current_round: data.round } : prev)
        break

      case 'range_updated':
        setCombat(prev => {
          if (!prev) return prev
          const ranges = (prev.ranges || []).map(r =>
            r.range_id === data.range_id ? data : r
          )
          return { ...prev, ranges }
        })
        break

      case 'combat_ended':
        setCombat(prev => prev ? { ...prev, status: 'ended' } : prev)
        injectCard('combat_phase', { round: '', phase: 'COMBAT ENDED', description: '' })
        break

      default:
        break
    }
  }, [wsLastMessage, injectCard])

  // ------------------------------------------------------------------
  // API actions
  // ------------------------------------------------------------------
  const startCombat = useCallback(async (styleOrObj = 'stat_only') => {
    // Accept either a string or {initiative_roll_style: ...} object
    const style = typeof styleOrObj === 'object' ? (styleOrObj.initiative_roll_style || 'stat_only') : styleOrObj
    const res = await fetch(
      `${API}/scenarios/${scenarioId}/combat/start?session_id=${sessionId}&token=${token}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initiative_roll_style: style }) }
    )
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    setCombat(data)
    return data
  }, [scenarioId, sessionId, token])

  const submitDeclaration = useCallback(async (params) => {
    const res = await fetch(`${API}/combats/${params.combat_id}/declare?token=${token}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }, [token])

  const rollChase = useCallback(async (combat_id, ship_id) => {
    const roll = Math.ceil(Math.random() * 6) + Math.ceil(Math.random() * 6) + Math.ceil(Math.random() * 6)
    const res = await fetch(`${API}/combats/${combat_id}/chase/roll?token=${token}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ship_id, roll }),
    })
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }, [token])

  const submitAttack = useCallback(async (params) => {
    const res = await fetch(
      `${API}/combats/${params.combat_id}/actions?session_id=${sessionId}&token=${token}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(params) }
    )
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }, [sessionId, token])

  const submitDefense = useCallback(async (combat_id, action_id, dodge_roll) => {
    const res = await fetch(
      `${API}/combats/${combat_id}/actions/${action_id}/defense?session_id=${sessionId}&token=${token}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ dodge_roll }) }
    )
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }, [sessionId, token])

  const submitDamage = useCallback(async (combat_id, action_id) => {
    const res = await fetch(
      `${API}/combats/${combat_id}/actions/${action_id}/damage?session_id=${sessionId}&token=${token}`,
      { method: 'POST', headers: { 'Content-Type': 'application/json' } }
    )
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }, [sessionId, token])

  const updateRange = useCallback(async (combat_id, range_id, fields) => {
    const res = await fetch(
      `${API}/combats/${combat_id}/ranges/${range_id}?session_id=${sessionId}&token=${token}`,
      { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ fields }) }
    )
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }, [sessionId, token])

  const endCombat = useCallback(async (combat_id) => {
    const res = await fetch(
      `${API}/combats/${combat_id}/end?session_id=${sessionId}&token=${token}`,
      { method: 'POST' }
    )
    if (!res.ok) throw new Error(await res.text())
    return res.json()
  }, [sessionId, token])

  return {
    combat, loading, error,
    startCombat, submitDeclaration, rollChase,
    submitAttack, submitDefense, submitDamage,
    updateRange, endCombat,
  }
}
