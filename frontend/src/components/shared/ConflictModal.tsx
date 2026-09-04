import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { AlertTriangle, Clock, Train as TrainIcon, ShieldAlert } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface ConflictModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ConflictModal({ isOpen, onClose }: ConflictModalProps) {
  const navigate = useNavigate();

  const conflicts = [
    {
      id: "CONF-01",
      severity: "critical",
      title: "12301 Rajdhani Priority Conflict on Block B2",
      description: "Unscheduled job J_UNSCHED_1 (Plain track tamping) requires 3h closure on B2, which would delay 12301 Rajdhani Express by 45 minutes.",
      resolution: "Deferred to Week 2 nocturnal traffic lull (02:00 to 05:00) to protect passenger punctuality.",
      affectedTrains: ["12301 Rajdhani Express"],
      blockId: "B2",
      status: "Resolved via Rescheduling"
    },
    {
      id: "CONF-02",
      severity: "warning",
      title: "Fixed Emergency Bridge Block FB1 on B1",
      description: "Emergency bridge repair requires strict 4h complete closure on B1 between 02:00 and 06:00. All regular traffic diverted to Loop 1.",
      resolution: "Immovable ghost-train constraint formulated in MILP solver. T6 RO-RO freight held at Hathras.",
      affectedTrains: ["T6 RO-RO Freight"],
      blockId: "B1",
      status: "Constraint Enforced"
    },
    {
      id: "CONF-03",
      severity: "warning",
      title: "Multi-Department Resource Clashing on B4",
      description: "OHE Job J1 and S&T Job J17 both required power cut on Section D to E. Scheduling sequentially would demand 4h closure.",
      resolution: "Synchronized into single 2.5h Shadow Block with joint safety earthing.",
      affectedTrains: ["T7 Purushottam Express"],
      blockId: "B4",
      status: "Consolidated via Shadow Block"
    }
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Active Conflicts & Constraint Log"
      description="Operational analysis of track occupancy contentions and solver resolution actions"
      maxWidth="xl"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button
            onClick={() => {
              onClose();
              navigate('/planner');
            }}
          >
            Inspect in Block Planner
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        {conflicts.map((conf) => (
          <div
            key={conf.id}
            className="p-4 rounded border border-neutral-200 bg-neutral-50/50 space-y-2.5"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                {conf.severity === "critical" ? (
                  <AlertTriangle className="w-4 h-4 text-op-red" />
                ) : (
                  <ShieldAlert className="w-4 h-4 text-op-amber" />
                )}
                <span className="font-bold text-neutral-900 text-xs sm:text-sm">
                  {conf.title}
                </span>
              </div>
              <Badge variant={conf.severity === "critical" ? "danger" : "warning"} size="sm">
                {conf.blockId}
              </Badge>
            </div>

            <p className="text-xs text-neutral-600 leading-relaxed">
              {conf.description}
            </p>

            <div className="p-2.5 bg-white rounded border border-neutral-200 text-xs">
              <span className="font-semibold text-neutral-800">Resolution: </span>
              <span className="text-neutral-700">{conf.resolution}</span>
            </div>

            <div className="flex items-center justify-between pt-1 text-[11px] text-neutral-500">
              <span className="flex items-center gap-1">
                <TrainIcon className="w-3.5 h-3.5" />
                Affected: {conf.affectedTrains.join(", ")}
              </span>
              <span className="flex items-center gap-1 font-mono text-op-green-dark">
                <Clock className="w-3 h-3" />
                {conf.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </Modal>
  );
}
