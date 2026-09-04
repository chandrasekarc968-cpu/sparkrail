import { useState, useEffect, useCallback } from "react";
import { Drawer } from "../ui/Drawer";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  AlertTriangle
} from "lucide-react";
import { ApiClient } from "../../api/client";
import type {
  AdvisoryProposal,
  ApprovalRole,
  ApprovalActionPayload,
  OperationalOverridePayload,
  AuditEventRecord
} from "../../api/types";

interface AdvisoryProposalDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  proposalId?: string;
  onProposalUpdated?: (updated: AdvisoryProposal) => void;
}

export function AdvisoryProposalDrawer({
  isOpen,
  onClose,
  proposalId,
  onProposalUpdated
}: AdvisoryProposalDrawerProps) {
  const [proposals, setProposals] = useState<AdvisoryProposal[]>([]);
  const [activeProposal, setActiveProposal] = useState<AdvisoryProposal | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"blocks" | "bundles" | "approval" | "regulation" | "audit">("blocks");
  const [auditEvents, setAuditEvents] = useState<AuditEventRecord[]>([]);

  // Approval Form State
  const [selectedRole, setSelectedRole] = useState<ApprovalRole>("CTPC");
  const [approverName, setApproverName] = useState("Chief Controller (HQ)");
  const [approverComments, setApproverComments] = useState("Sanctioned pursuant to IR General & Subsidiary Rules.");
  const [actionLoading, setActionLoading] = useState(false);

  // Override Form State
  const [showOverrideForm, setShowOverrideForm] = useState(false);
  const [overrideReason, setOverrideReason] = useState("EMERGENCY_DERAILMENT_RISK");
  const [overrideJustification, setOverrideJustification] = useState("");

  const loadProposals = useCallback(async () => {
    setLoading(true);
    try {
      const list = await ApiClient.getAdvisoryProposals();
      setProposals(list);
      if (list.length > 0) {
        if (proposalId) {
          const matched = list.find((p) => p.optimization_run_id === proposalId);
          setActiveProposal(matched || list[0]);
        } else {
          setActiveProposal(list[0]);
        }
      }
      const audits = await ApiClient.getAuditTrail(50);
      setAuditEvents(audits);
    } catch (err) {
      console.error("Failed to fetch advisory proposals:", err);
    } finally {
      setLoading(false);
    }
  }, [proposalId]);

  useEffect(() => {
    if (isOpen) {
      loadProposals();
    }
  }, [isOpen, loadProposals]);

  const handleApprove = async () => {
    if (!activeProposal) return;
    setActionLoading(true);
    try {
      const payload: ApprovalActionPayload = {
        role: selectedRole,
        approver_id: `EMP-${selectedRole}-01`,
        approver_name: approverName,
        decision: "APPROVED",
        comments: approverComments
      };
      const updated = await ApiClient.approveProposal(activeProposal.optimization_run_id, payload);
      setActiveProposal(updated);
      if (onProposalUpdated) onProposalUpdated(updated);
      loadProposals();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Approval failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!activeProposal) return;
    setActionLoading(true);
    try {
      const payload: ApprovalActionPayload = {
        role: selectedRole,
        approver_id: `EMP-${selectedRole}-01`,
        approver_name: approverName,
        decision: "REJECTED",
        comments: approverComments || "Rejected due to operational constraints."
      };
      const updated = await ApiClient.rejectProposal(activeProposal.optimization_run_id, payload);
      setActiveProposal(updated);
      if (onProposalUpdated) onProposalUpdated(updated);
      loadProposals();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Rejection failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleOverride = async () => {
    if (!activeProposal || !overrideJustification.trim()) {
      alert("Mandatory justification is required for statutory operational override.");
      return;
    }
    setActionLoading(true);
    try {
      const payload: OperationalOverridePayload = {
        user_id: `DISPATCHER-${selectedRole}`,
        role: selectedRole,
        reason_code: overrideReason,
        justification: overrideJustification,
        overridden_schedule: { recommended_blocks: activeProposal.recommended_blocks }
      };
      const res = await ApiClient.overrideProposal(activeProposal.optimization_run_id, payload);
      setActiveProposal(res.updated_proposal);
      setShowOverrideForm(false);
      if (onProposalUpdated) onProposalUpdated(res.updated_proposal);
      loadProposals();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Override failed");
    } finally {
      setActionLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title="BDMS Advisory Schedule Review"
      subtitle={activeProposal ? `${activeProposal.optimization_run_id} • ${activeProposal.division_code}` : "Loading proposals..."}
      width="xl"
    >
      <div className="space-y-6">
        {/* Advisory Safety Boundary Banner */}
        <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-900 flex items-start space-x-3">
          <ShieldAlert className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="text-xs space-y-1">
            <p className="font-bold uppercase tracking-wider text-amber-700">
              Statutory Advisory Gate • Outbound BDMS Proposal
            </p>
            <p className="text-neutral-700">
              This schedule is strictly advisory and cannot operate switches, clear signals, or isolate power directly. 
              Physical execution requires formal BDMS approval by the designated controllers.
            </p>
          </div>
        </div>

        {loading && (
          <div className="p-3 bg-neutral-100 rounded text-xs text-neutral-600 animate-pulse">
            Fetching latest BDMS proposals and audit trail from advisory layer...
          </div>
        )}

        {/* Proposal Selector & Metadata Header */}
        {activeProposal && (
          <div className="bg-neutral-50 rounded-lg p-4 border border-neutral-200 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <span className="text-xs font-semibold text-neutral-500">Proposal Run:</span>
                <select
                  aria-label="Select Advisory Proposal"
                  value={activeProposal.optimization_run_id}
                  onChange={(e) => {
                    const found = proposals.find((p) => p.optimization_run_id === e.target.value);
                    if (found) setActiveProposal(found);
                  }}
                  className="text-xs font-mono font-medium bg-white border border-neutral-300 rounded px-2 py-1 text-neutral-900"
                >
                  {proposals.map((p) => (
                    <option key={p.optimization_run_id} value={p.optimization_run_id}>
                      {p.optimization_run_id} ({p.approval_status})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center space-x-2">
                <Badge
                  variant={
                    activeProposal.approval_status === "SANCTIONED"
                      ? "success"
                      : activeProposal.approval_status === "REJECTED"
                      ? "danger"
                      : activeProposal.approval_status === "OVERRIDDEN"
                      ? "warning"
                      : "info"
                  }
                >
                  {activeProposal.approval_status}
                </Badge>
                <Badge
                  variant={activeProposal.safety_status === "SAFETY_CERTIFIED" ? "success" : "danger"}
                >
                  {activeProposal.safety_status}
                </Badge>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-neutral-200 text-xs">
              <div>
                <span className="text-neutral-500 block">Solver Tier</span>
                <span className="font-semibold text-neutral-900">{activeProposal.solver_mode}</span>
              </div>
              <div>
                <span className="text-neutral-500 block">Horizon</span>
                <span className="font-semibold text-neutral-900">{activeProposal.planning_window}</span>
              </div>
              <div>
                <span className="text-neutral-500 block">Closure Hours</span>
                <span className="font-semibold text-neutral-900">
                  {activeProposal.computed_metrics.total_closure_hours.toFixed(1)} hrs
                </span>
              </div>
              <div>
                <span className="text-neutral-500 block">Total TCI</span>
                <span className="font-semibold text-neutral-900">
                  {activeProposal.computed_metrics.objective_tci_value.toFixed(1)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex border-b border-neutral-200 text-xs font-medium space-x-4">
          <button
            onClick={() => setActiveTab("blocks")}
            className={`pb-2 transition-colors ${
              activeTab === "blocks"
                ? "border-b-2 border-emerald-600 text-emerald-600 font-bold"
                : "text-neutral-500 hover:text-neutral-900"
            }`}
          >
            Recommended Blocks ({activeProposal?.recommended_blocks.length || 0})
          </button>
          <button
            onClick={() => setActiveTab("bundles")}
            className={`pb-2 transition-colors ${
              activeTab === "bundles"
                ? "border-b-2 border-emerald-600 text-emerald-600 font-bold"
                : "text-neutral-500 hover:text-neutral-900"
            }`}
          >
            Shadow Bundles ({activeProposal?.candidate_bundles.length || 0})
          </button>
          <button
            onClick={() => setActiveTab("approval")}
            className={`pb-2 transition-colors ${
              activeTab === "approval"
                ? "border-b-2 border-emerald-600 text-emerald-600 font-bold"
                : "text-neutral-500 hover:text-neutral-900"
            }`}
          >
            Approval Chain
          </button>
          <button
            onClick={() => setActiveTab("regulation")}
            className={`pb-2 transition-colors ${
              activeTab === "regulation"
                ? "border-b-2 border-emerald-600 text-emerald-600 font-bold"
                : "text-neutral-500 hover:text-neutral-900"
            }`}
          >
            Train Regulation
          </button>
          <button
            onClick={() => setActiveTab("audit")}
            className={`pb-2 transition-colors ${
              activeTab === "audit"
                ? "border-b-2 border-emerald-600 text-emerald-600 font-bold"
                : "text-neutral-500 hover:text-neutral-900"
            }`}
          >
            Audit Trail
          </button>
        </div>

        {/* Tab 1: Recommended Blocks */}
        {activeTab === "blocks" && activeProposal && (
          <div className="space-y-3">
            <div className="space-y-2">
              {activeProposal.recommended_blocks.map((b, idx) => (
                <div
                  key={`${b.job_id}-${idx}`}
                  className="p-3 bg-white border border-neutral-200 rounded-lg shadow-sm hover:border-emerald-300 transition-all flex items-center justify-between"
                >
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-mono font-bold text-xs text-neutral-900">{b.job_id}</span>
                      <span className="text-xs text-neutral-500">Block {b.block_id}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {b.department}
                      </Badge>
                      {b.is_shadow && (
                        <span className="text-[10px] bg-indigo-50 text-indigo-700 font-semibold px-1.5 py-0.5 rounded border border-indigo-200">
                          SHADOW
                        </span>
                      )}
                    </div>
                    <div className="text-[11px] text-neutral-500 flex items-center space-x-3">
                      <span>Window: T+{b.start_time}h to T+{b.end_time}h</span>
                      <span>Duration: {(b.end_time - b.start_time).toFixed(1)}h</span>
                      <span>TCI: {b.tci.toFixed(1)}</span>
                    </div>
                  </div>

                  <div>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-semibold ${
                        b.lifecycle_state === "GRANTED"
                          ? "bg-emerald-100 text-emerald-800"
                          : b.lifecycle_state === "SANCTIONED"
                          ? "bg-blue-100 text-blue-800"
                          : b.lifecycle_state === "IN_PROGRESS"
                          ? "bg-purple-100 text-purple-800"
                          : b.lifecycle_state === "REJECTED"
                          ? "bg-red-100 text-red-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {b.lifecycle_state}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Diagnostics checklist */}
            <div className="p-3 bg-neutral-50 rounded border border-neutral-200 text-xs space-y-1">
              <span className="font-semibold text-neutral-700 block">Microscopic Safety Diagnostics:</span>
              {activeProposal.diagnostics.map((d, i) => (
                <div key={i} className="flex items-center space-x-1.5 text-neutral-600">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" />
                  <span>{d}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 2: Candidate Bundles */}
        {activeTab === "bundles" && activeProposal && (
          <div className="space-y-3">
            {activeProposal.candidate_bundles.length === 0 ? (
              <p className="text-xs text-neutral-500 italic">No shadow bundles generated in this run.</p>
            ) : (
              activeProposal.candidate_bundles.map((bundle) => (
                <div
                  key={bundle.bundle_id}
                  className="p-3 bg-white border border-neutral-200 rounded-lg shadow-sm space-y-2"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono font-bold text-xs text-neutral-900">{bundle.bundle_id}</span>
                    <Badge variant="info" className="text-[10px]">
                      {bundle.departments.join(" + ")}
                    </Badge>
                  </div>
                  <p className="text-xs text-neutral-700">{bundle.compatibility_rationale}</p>
                  <div className="flex items-center justify-between text-[11px] text-neutral-500 pt-2 border-t border-neutral-100">
                    <span>Primary: {bundle.primary_job_id}</span>
                    <span>Secondary: {bundle.secondary_job_ids.join(", ") || "None"}</span>
                    <span>Benefit: +{bundle.total_tci_benefit.toFixed(1)} TCI</span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Tab 3: Approval Chain & Actions */}
        {activeTab === "approval" && activeProposal && (
          <div className="space-y-4">
            <div className="bg-white border border-neutral-200 rounded-lg p-3 space-y-3">
              <h4 className="text-xs font-bold text-neutral-900 uppercase tracking-wider">
                Statutory Approval Hierarchy
              </h4>
              <div className="space-y-2">
                {Object.entries(activeProposal.approval_chain).map(([role, rec]) => (
                  <div
                    key={role}
                    className="flex items-center justify-between p-2 rounded bg-neutral-50 border border-neutral-200 text-xs"
                  >
                    <div>
                      <span className="font-bold text-neutral-800">{role}</span>
                      {rec.approver_name && (
                        <span className="text-neutral-500 text-[11px] ml-2">by {rec.approver_name}</span>
                      )}
                      {rec.comments && (
                        <p className="text-[11px] text-neutral-600 italic mt-0.5">{rec.comments}</p>
                      )}
                    </div>
                    <div>
                      <Badge
                        variant={
                          rec.status === "APPROVED"
                            ? "success"
                            : rec.status === "REJECTED"
                            ? "danger"
                            : "outline"
                        }
                      >
                        {rec.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Approval Action Form */}
            <div className="bg-neutral-50 border border-neutral-200 rounded-lg p-3 space-y-3">
              <h4 className="text-xs font-bold text-neutral-900">Sign-Off or Reject as Controller</h4>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <label className="block text-neutral-600 mb-1">Your Role</label>
                  <select
                    value={selectedRole}
                    onChange={(e) => setSelectedRole(e.target.value as ApprovalRole)}
                    className="w-full bg-white border border-neutral-300 rounded px-2 py-1"
                  >
                    <option value="CTPC">CTPC (Chief Track Possession Controller)</option>
                    <option value="SR_DOM">Sr. DOM (Divisional Operations Manager)</option>
                    <option value="SECTION_CONTROLLER">Section Controller</option>
                    <option value="STATION_MASTER">Station Master</option>
                  </select>
                </div>
                <div>
                  <label className="block text-neutral-600 mb-1">Controller Name</label>
                  <input
                    type="text"
                    value={approverName}
                    onChange={(e) => setApproverName(e.target.value)}
                    className="w-full bg-white border border-neutral-300 rounded px-2 py-1"
                  />
                </div>
              </div>

              <div>
                <label className="block text-neutral-600 text-xs mb-1">Statutory Comments / Reason</label>
                <input
                  type="text"
                  value={approverComments}
                  onChange={(e) => setApproverComments(e.target.value)}
                  className="w-full bg-white border border-neutral-300 rounded px-2 py-1 text-xs"
                />
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <Button
                  size="sm"
                  onClick={handleApprove}
                  disabled={actionLoading}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1" />
                  Approve as {selectedRole}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleReject}
                  disabled={actionLoading}
                  className="text-red-600 border-red-200 hover:bg-red-50 text-xs"
                >
                  <XCircle className="w-3.5 h-3.5 mr-1" />
                  Reject Proposal
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowOverrideForm(!showOverrideForm)}
                  className="text-amber-700 border-amber-300 hover:bg-amber-50 text-xs ml-auto"
                >
                  <AlertTriangle className="w-3.5 h-3.5 mr-1" />
                  Operational Override
                </Button>
              </div>

              {/* Collapsible Operational Override Form */}
              {showOverrideForm && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded mt-3 space-y-2 text-xs">
                  <span className="font-bold text-amber-900 block">
                    Statutory Operational Override (Audited & Logged)
                  </span>
                  <div>
                    <label className="block text-amber-800 mb-1">Override Reason Code</label>
                    <select
                      value={overrideReason}
                      onChange={(e) => setOverrideReason(e.target.value)}
                      className="w-full bg-white border border-amber-300 rounded px-2 py-1"
                    >
                      <option value="EMERGENCY_DERAILMENT_RISK">EMERGENCY_DERAILMENT_RISK (Safety Flash)</option>
                      <option value="VIP_MOVEMENT">VIP_MOVEMENT (Protocol Schedule Clear)</option>
                      <option value="ADVERSE_WEATHER">ADVERSE_WEATHER (Dense Fog / High Temp Alert)</option>
                      <option value="ROLLING_STOCK_DEFECT">ROLLING_STOCK_DEFECT (En-route Break-down)</option>
                      <option value="LOCAL_CONTROLLER_DISCRETION">LOCAL_CONTROLLER_DISCRETION (Operating Ground)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-amber-800 mb-1">Mandatory Operational Justification</label>
                    <textarea
                      rows={2}
                      value={overrideJustification}
                      onChange={(e) => setOverrideJustification(e.target.value)}
                      placeholder="Explain operational necessity with station control log reference..."
                      className="w-full bg-white border border-amber-300 rounded p-1.5 text-xs"
                    />
                  </div>
                  <Button
                    size="sm"
                    onClick={handleOverride}
                    disabled={actionLoading}
                    className="bg-amber-600 hover:bg-amber-700 text-white text-xs w-full"
                  >
                    Confirm & Record Override
                  </Button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 4: Train Regulation Plan */}
        {activeTab === "regulation" && activeProposal && (
          <div className="space-y-3">
            <p className="text-xs text-neutral-500">
              Downstream regulation schedule generated by Microscopic Dispatch Validator:
            </p>
            <div className="space-y-2">
              {Object.entries(activeProposal.train_regulation_plan).map(([trainId, reg]) => (
                <div
                  key={trainId}
                  className="p-2.5 bg-white border border-neutral-200 rounded flex items-center justify-between text-xs"
                >
                  <div>
                    <span className="font-bold text-neutral-900">{trainId}</span>
                    <span className="text-neutral-500 block text-[11px]">
                      Delay: {(reg.accumulated_delay_hours * 60).toFixed(0)} mins
                    </span>
                  </div>
                  <Badge
                    variant={reg.regulation_strategy === "RUN_THROUGH" ? "success" : "warning"}
                  >
                    {reg.regulation_strategy}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tab 5: Audit Trail */}
        {activeTab === "audit" && (
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-neutral-900 uppercase tracking-wider">
              Statutory Tamper-Evident Audit Records
            </h4>
            <div className="space-y-1.5">
              {auditEvents.map((evt) => (
                <div
                  key={evt.id || evt.event_id}
                  className="p-2 bg-neutral-50 border border-neutral-200 rounded text-xs space-y-0.5 font-mono"
                >
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-bold text-neutral-800">{evt.event_type}</span>
                    <span className="text-neutral-400">{evt.timestamp}</span>
                  </div>
                  <div className="text-[11px] text-neutral-600">
                    User: {evt.user_id} ({evt.role}) • Action: {evt.action}
                  </div>
                  {evt.details && Object.keys(evt.details).length > 0 && (
                    <div className="text-[10px] text-neutral-500 truncate">
                      {JSON.stringify(evt.details)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Drawer>
  );
}
