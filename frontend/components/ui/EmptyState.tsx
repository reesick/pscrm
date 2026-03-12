export function EmptyState({ message, icon = "📭" }: { message: string; icon?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-64 text-gray-400">
      <span className="text-4xl mb-3">{icon}</span>
      <p className="text-sm text-center max-w-xs">{message}</p>
    </div>
  );
}
