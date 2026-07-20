"use client";

export default function LoadingSkeleton() {
  return (
    <div className="card space-y-4 mt-6 animate-pulse">
      {/* Header */}
      <div className="flex items-center gap-3 pb-4 border-b border-gray-100">
        <div className="skeleton w-12 h-12 rounded-xl" />
        <div className="flex-1 space-y-2">
          <div className="skeleton h-5 w-32 rounded" />
          <div className="skeleton h-3.5 w-20 rounded" />
        </div>
        <div className="skeleton h-6 w-20 rounded-full" />
      </div>

      {/* Rows */}
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex justify-between items-center py-1">
          <div className="skeleton h-3.5 rounded" style={{ width: `${80 + i * 10}px` }} />
          <div className="skeleton h-3.5 rounded" style={{ width: `${60 + i * 15}px` }} />
        </div>
      ))}

      {/* Tax section */}
      <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
        <div className="skeleton h-4 w-28 rounded" />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex justify-between">
            <div className="skeleton h-3.5 w-24 rounded" />
            <div className="skeleton h-3.5 w-28 rounded" />
          </div>
        ))}
        <div className="skeleton h-12 w-full rounded-xl mt-2" />
      </div>
    </div>
  );
}
