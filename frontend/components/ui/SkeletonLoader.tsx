export function ComplaintListSkeleton() {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="animate-pulse border border-gray-100 rounded p-3">
          <div className="h-3 bg-gray-200 rounded w-1/3 mb-2" />
          <div className="h-2 bg-gray-100 rounded w-2/3" />
        </div>
      ))}
    </div>
  );
}

export function PanelSkeleton() {
  return (
    <div className="p-6 space-y-4 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-1/4 mb-4" />
      <div className="h-6 bg-gray-200 rounded w-3/4 mb-2" />
      <div className="h-20 bg-gray-100 rounded w-full mb-4" />
      <div className="h-10 bg-gray-200 rounded w-full" />
    </div>
  );
}
