export function SkeletonCard({ lines = 3 }) {
  return (
    <div className="card p-4 space-y-3">
      <div className="skeleton h-4 rounded w-3/4" />
      {Array.from({ length: lines - 1 }).map((_, i) => (
        <div key={i} className="skeleton h-3 rounded" style={{ width: `${60 + Math.random() * 30}%` }} />
      ))}
    </div>
  )
}
