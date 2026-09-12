import { useState } from 'react';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { ApiClient } from '../../api/client';
import { Download, Printer, FileText, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  runId?: string;
  divisionCode?: string;
}

export function ExportModal({ isOpen, onClose, runId, divisionCode = "PRYJ" }: ExportModalProps) {
  const [selectedFormat, setSelectedFormat] = useState<'json' | 'csv' | 'html'>('json');
  const [isExporting, setIsExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);

  const handleExport = async () => {
    setIsExporting(true);
    setExportSuccess(false);
    try {
      const content = await ApiClient.exportAdvisorySchedule(selectedFormat, runId);
      if (selectedFormat === 'html') {
        const printWindow = window.open('', '_blank');
        if (printWindow) {
          printWindow.document.write(content);
          printWindow.document.close();
          printWindow.focus();
        }
      } else {
        const mimeType = selectedFormat === 'json' ? 'application/json' : 'text/csv';
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sparkrail_advisory_${divisionCode}_${runId || 'schedule'}.${selectedFormat}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
      setExportSuccess(true);
    } catch (err) {
      console.error("Export failed:", err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Export Statutory Advisory Schedule Package">
      <div className="space-y-4 text-xs">
        <div className="p-3 bg-amber-50 border border-amber-200 rounded text-amber-900 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold">ADVISORY ONLY: HUMAN APPROVAL REQUIRED</span>
            <p className="text-[11px] text-amber-800 mt-0.5">
              Exported schedules represent algorithmic decision-support packages only.
              They must be reviewed and signed off by CTPC, Sr. DOM, Section Controller,
              and Station Master prior to any physical track possession.
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <label className="font-bold text-neutral-700">Choose Export Format:</label>
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => setSelectedFormat('json')}
              className={`p-3 border rounded text-left transition-colors flex flex-col items-start gap-1 ${
                selectedFormat === 'json'
                  ? 'border-accent-600 bg-accent-50 text-accent-950 font-bold'
                  : 'border-neutral-200 hover:bg-neutral-50 text-neutral-700'
              }`}
            >
              <FileText className="w-4 h-4 text-accent-600" />
              <span>JSON Package</span>
              <span className="text-[10px] text-neutral-500 font-normal">Machine-readable BDMS format</span>
            </button>

            <button
              type="button"
              onClick={() => setSelectedFormat('csv')}
              className={`p-3 border rounded text-left transition-colors flex flex-col items-start gap-1 ${
                selectedFormat === 'csv'
                  ? 'border-accent-600 bg-accent-50 text-accent-950 font-bold'
                  : 'border-neutral-200 hover:bg-neutral-50 text-neutral-700'
              }`}
            >
              <Download className="w-4 h-4 text-accent-600" />
              <span>CSV Spreadsheet</span>
              <span className="text-[10px] text-neutral-500 font-normal">Tabular track block schedule</span>
            </button>

            <button
              type="button"
              onClick={() => setSelectedFormat('html')}
              className={`p-3 border rounded text-left transition-colors flex flex-col items-start gap-1 ${
                selectedFormat === 'html'
                  ? 'border-accent-600 bg-accent-50 text-accent-950 font-bold'
                  : 'border-neutral-200 hover:bg-neutral-50 text-neutral-700'
              }`}
            >
              <Printer className="w-4 h-4 text-accent-600" />
              <span>Printable Docket</span>
              <span className="text-[10px] text-neutral-500 font-normal">Official IR Sign-off format</span>
            </button>
          </div>
        </div>

        <div className="bg-neutral-50 p-3 rounded border border-neutral-200 space-y-1 font-mono text-[11px]">
          <div>Corridor: Subedarganj (SFG) – Mirzapur (MZP)</div>
          <div>Division: {divisionCode}</div>
          <div>Run ID: {runId || "RUN-SYNTH-DEMO-01"}</div>
          <div className="flex items-center gap-1 mt-1 text-emerald-700">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Cryptographic SHA-256 Provenance Embedded</span>
          </div>
        </div>

        {exportSuccess && (
          <div className="p-2.5 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>Advisory package successfully generated and downloaded!</span>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-neutral-200">
          <Button variant="outline" size="sm" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="default"
            size="sm"
            onClick={handleExport}
            disabled={isExporting}
            className="flex items-center gap-1.5"
          >
            {isExporting ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Generating...
              </>
            ) : selectedFormat === 'html' ? (
              <>
                <Printer className="w-3.5 h-3.5" />
                Open Printable Docket
              </>
            ) : (
              <>
                <Download className="w-3.5 h-3.5" />
                Download {selectedFormat.toUpperCase()}
              </>
            )}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
