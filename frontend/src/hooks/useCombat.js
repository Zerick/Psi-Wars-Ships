// hooks/useCombat.js
import { useState, useEffect, useCallback } from "react";

const API = import.meta.env.VITE_API_URL || "";

function uid() { return Math.random().toString(36).slice(2) }

export function useCombat({ sessionId, token, scenarioId, isGm, wsLastMessage, onInjectLog }) {
  const [combat,  setCombat]  = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

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

  const injectCard = useCallback((type, data) => {
    if (!onInjectLog) return
    onInjectLog({ entry_id: uid(), entry_type: type, data })
  }, [onInjectLog])

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
          phase: (data.phase || '').toUpperCase().replace(/_/g, ' '),
          description: phaseLabels[data.phase] || '',
        })
        break
      }

      case 'chase_phase_started': {
        // Inject one Roll card per ship — GM presses button for each
        setCombat(prev => prev ? { ...prev, current_phase: 'chase', current_round: data.round } : prev)
        ;(data.ships || []).forEach(ship => {
          injectCard('combat_chase', {
            combat_card_id: `chase-${data.combat_id}-r${data.round}-${ship.ship_id}`,
            combat_id:      data.combat_id,
            ship_id:        ship.ship_id,
            ship_name:      ship.ship_name,
            chase_bonus:    ship.chase_bonus,
            breakdown:      ship.breakdown,
            npc:            ship.npc,
            faction:        ship.faction,
            owner_user_id:  ship.owner_user_id,
            rolled:         false,
            roll:           null,
            mos:            null,
          })
        })
        break
      }

      case 'chase_roll_submitted': {
        // Update matching chase card in-place
        if (onInjectLog) {
          onInjectLog({
            entry_type: '__chase_roll_update__',
            combat_id:  data.combat_id,
            ship_id:    data.ship_id,
            roll:       data.roll,
            bonus:      data.bonus,
            mos:        data.mos,
          })
        }
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

      case 'chase_resolved':
        setCombat(prev => prev ? { ...prev, ranges: data.updated_ranges } : prev)
        if (data.updated_ranges) {
          const r = data.updated_ranges[0]
          if (r) {
            injectCard('combat_chase_resolution', {
              winner:      r.advantage_ship_id ? 'Advantage gained' : 'No advantage',
              loser:       '',
              new_range:   r.range_band,
              description: `Range: ${r.range_band}${r.matched_speed ? ' · Matched Speed' : ''}`,
            })
          }
        }
        break

      case 'action_submitted':
        injectCard('combat_attack', {
          combat_card_id: `attack-${data.action_id}`,
          action_id:      data.action_id,
          combat_id:      data.combat_id,
          ship_id:        data.acting_ship_id,
          ship_name:      data.acting_ship_name || 'Attacker',
          target_name:    data.target_ship_name || 'Target',
          weapon_name:    data.weapon_name || 'Weapon',
          attack_bonus:   data.attack_total,
          breakdown:      data.attack_modifiers
            ? Object.entries(data.attack_modifiers || {}).map(([k,v]) => ({ label: k, value: v }))
            : [],
          npc:    true,
          rolled: true,
          roll:   data.attack_roll,
          hit:    data.attack_hit,
        })
        break

      case 'defense_submitted':
        injectCard('combat_dodge', {
          combat_card_id: `dodge-${data.action_id}`,
          action_id:  data.action_id,
          ship_name:  data.target_ship_name || 'Defender',
          attacker_name: data.acting_ship_name || 'Attacker',
          dodge_bonus: data.dodge_total || 9,
          npc:    true,
          rolled: true,
          roll:   data.dodge_roll,
          dodged: data.dodge_success,
        })
        break

      case 'damage_submitted':
        injectCard('combat_damage', {
          ship_name:     data.target_ship_name || 'Target',
          attacker_name: data.acting_ship_name || 'Attacker',
          damage_rolled: data.damage_raw,
          damage_net:    data.damage_net,
          hp_before:     data.hp_before,
          hp_after:      data.hp_after,
          screen_before: data.screen_before,
          screen_after:  data.screen_after,
          wound_after:   data.wound_level_after,
          description:   data.wound_level_after ? `Wound: ${data.wound_level_after}` : '',
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
        injectCard('combat_phase', {
          round: data.round - 1,
          phase: 'ROUND COMPLETE',
          description: `Beginning Round ${data.round}`,
        })
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
  }, [wsLastMessage, injectCard, onInjectLog])

  const startCombat = useCallback(async (styleOrObj = 'stat_only') => {
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
    const roll = Math.ceil(Math.random()*6) + Math.ceil(Math.random()*6) + Math.ceil(Math.random()*6)
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
