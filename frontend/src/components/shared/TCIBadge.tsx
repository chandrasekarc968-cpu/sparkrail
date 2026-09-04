import { Badge } from "../ui/Badge";

interface TCIBadgeProps {
  score: number;
  showLabel?: boolean;
  size?: "sm" | "default";
}

export function TCIBadge({ score, showLabel = true, size = "default" }: TCIBadgeProps) {
  let variant: "danger" | "warning" | "info" | "success";
  let label: string;

  if (score >= 80) {
    variant = "danger";
    label = "CRITICAL";
  } else if (score >= 60) {
    variant = "warning";
    label = "HIGH";
  } else if (score >= 40) {
    variant = "info";
    label = "MEDIUM";
  } else {
    variant = "success";
    label = "LOW";
  }

  return (
    <Badge
      variant={variant}
      size={size}
      aria-label={`Task Criticality Index ${score.toFixed(1)}, level ${label}`}
      className="tabular-nums"
    >
      <span className="font-bold mr-1">{score.toFixed(1)}</span>
      {showLabel && (
        <span className="text-[9px] uppercase tracking-wider opacity-90 border-l border-current/30 pl-1">
          {label}
        </span>
      )}
    </Badge>
  );
}
