// =============================================================================
// RoleTag.jsx — Participant name + role badge
// =============================================================================
export default function RoleTag({ displayName, role }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
      <span style={{ color: 'var(--text-primary)' }}>{displayName}</span>
      <span className={`badge badge-${role}`}>{role}</span>
    </span>
  )
}
