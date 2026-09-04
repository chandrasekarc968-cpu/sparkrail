import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "./Button";

interface ErrorBannerProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  isRetrying?: boolean;
}

export function ErrorBanner({
  title = "Backend Request Failed",
  message,
  onRetry,
  isRetrying = false,
}: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="border border-op-red/30 bg-op-red/10 rounded-md p-4 text-neutral-900 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
    >
      <div className="flex items-start space-x-3">
        <AlertTriangle className="w-5 h-5 text-op-red shrink-0 mt-0.5" aria-hidden="true" />
        <div>
          <h4 className="text-sm font-semibold text-op-red-dark">{title}</h4>
          <p className="text-xs text-neutral-700 mt-0.5">{message}</p>
        </div>
      </div>
      {onRetry && (
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          isLoading={isRetrying}
          className="border-op-red/40 text-op-red-dark hover:bg-op-red/10 shrink-0"
        >
          <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
          Retry Request
        </Button>
      )}
    </div>
  );
}
