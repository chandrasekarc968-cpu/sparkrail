import type {
  NetworkGeometryResponse,
  Coordinate3D,
  CoordinateSystemContract
} from './types';

export const CANONICAL_GEOMETRY_SCHEMA_VERSION = "1.0.0";

export const CANONICAL_COORDINATE_SYSTEM: CoordinateSystemContract = {
  name: "LOCAL_CORRIDOR",
  crs: "LOCAL_CORRIDOR",
  units: "meters",
  axis_order: ["x", "y", "z"],
  handedness: "right-handed",
  origin_description: "Synthetic local origin for the bounded railway division",
  geometry_source: "synthetic"
};

export class GeometryContractError extends Error {
  public readonly schemaVersion: string;
  public readonly details: string[];

  constructor(message: string, schemaVersion: string = "1.0.0", details: string[] = []) {
    super(`[Geometry Contract Violation (v${schemaVersion})]: ${message}`);
    this.name = 'GeometryContractError';
    this.schemaVersion = schemaVersion;
    this.details = details;
  }
}

function isValidFiniteCoord(coord: unknown): coord is Coordinate3D {
  if (!coord || typeof coord !== 'object') return false;
  const c = coord as Record<string, unknown>;
  return (
    typeof c.x === 'number' && Number.isFinite(c.x) &&
    typeof c.y === 'number' && Number.isFinite(c.y) &&
    typeof c.z === 'number' && Number.isFinite(c.z)
  );
}

export function validateCoordinateSystemContract(cs: unknown, expectedVersion: string = "1.0.0"): CoordinateSystemContract {
  if (!cs || typeof cs !== 'object') {
    throw new GeometryContractError("Missing or invalid 'coordinate_system' object in geometry payload", expectedVersion);
  }
  const c = cs as Record<string, unknown>;
  const errors: string[] = [];

  const allowedCRSs = ['LOCAL_CORRIDOR', 'EPSG:4326'];
  if (!c.crs || !allowedCRSs.includes(String(c.crs))) {
    errors.push(`coordinate_system.crs must be one of [${allowedCRSs.join(', ')}], got '${c.crs}'`);
  }
  if (c.crs === 'LOCAL_CORRIDOR' && c.units !== 'meters') {
    errors.push(`coordinate_system.units must be 'meters' for LOCAL_CORRIDOR, got '${c.units}'`);
  }
  if (!Array.isArray(c.axis_order) || c.axis_order.length !== 3) {
    errors.push(`coordinate_system.axis_order must have 3 elements, got ${JSON.stringify(c.axis_order)}`);
  }
  if (c.handedness !== 'right-handed') {
    errors.push(`coordinate_system.handedness must be 'right-handed', got '${c.handedness}'`);
  }
  if (c.geometry_source !== 'synthetic' && c.geometry_source !== 'surveyed' && c.geometry_source !== 'authoritative') {
    errors.push(`coordinate_system.geometry_source must be 'synthetic', 'surveyed', or 'authoritative', got '${c.geometry_source}'`);
  }

  if (errors.length > 0) {
    throw new GeometryContractError(errors.join('; '), expectedVersion, errors);
  }

  return cs as CoordinateSystemContract;
}

export function validateNetworkGeometryContract(
  data: unknown,
  isDemo: boolean = false
): NetworkGeometryResponse {
  if (!data || typeof data !== 'object') {
    throw new GeometryContractError("Geometry payload must be a non-null object", "1.0.0");
  }

  const payload = data as Record<string, unknown>;
  const version = payload.geometry_schema_version;

  // 1. Enforce geometry_schema_version: "1.0.0"
  if (typeof version !== 'string' || !version.trim()) {
    throw new GeometryContractError(
      "Missing required 'geometry_schema_version' field. Expected '1.0.0'",
      "unknown"
    );
  }

  const [major] = version.split('.');
  if (major !== '1') {
    throw new GeometryContractError(
      `Incompatible geometry_schema_version '${version}'. Expected major version 1 (contract version '1.0.0')`,
      version
    );
  }

  // 2. Validate Coordinate System Contract
  validateCoordinateSystemContract(payload.coordinate_system, version);

  // 3. Tracks & Nodes validation
  if (!Array.isArray(payload.tracks) || payload.tracks.length === 0) {
    throw new GeometryContractError("Geometry payload must contain non-empty 'tracks' array", version);
  }
  if (!Array.isArray(payload.nodes) || payload.nodes.length === 0) {
    throw new GeometryContractError("Geometry payload must contain non-empty 'nodes' array", version);
  }

  // Check track coordinates
  for (let i = 0; i < payload.tracks.length; i++) {
    const track = payload.tracks[i] as Record<string, unknown>;
    const blockId = String(track.block_id || `track[${i}]`);
    if (!isValidFiniteCoord(track.start_coord)) {
      throw new GeometryContractError(`Track '${blockId}' has non-finite or missing 'start_coord'. The frontend must never invent track geometry.`, version);
    }
    if (!isValidFiniteCoord(track.end_coord)) {
      throw new GeometryContractError(`Track '${blockId}' has non-finite or missing 'end_coord'. The frontend must never invent track geometry.`, version);
    }
    if (!Array.isArray(track.path_points) || track.path_points.length < 2) {
      throw new GeometryContractError(`Track '${blockId}' must have at least 2 path points`, version);
    }
    for (let pIdx = 0; pIdx < track.path_points.length; pIdx++) {
      if (!isValidFiniteCoord(track.path_points[pIdx])) {
        throw new GeometryContractError(
          `Track '${blockId}' path_point[${pIdx}] has non-finite coordinates`,
          version
        );
      }
    }
  }

  // Check station node coordinates
  for (let i = 0; i < payload.nodes.length; i++) {
    const node = payload.nodes[i] as Record<string, unknown>;
    const nodeId = String(node.id || `node[${i}]`);
    const pos = node.position || node.coordinates;
    if (!isValidFiniteCoord(pos)) {
      if (!isDemo) {
        throw new GeometryContractError(
          `Node '${nodeId}' has non-finite or missing coordinates. The frontend must never invent station geometry in non-demo mode.`,
          version
        );
      }
    }
  }

  // 4. Canonical TrackSections validation (if present)
  if (Array.isArray(payload.track_sections)) {
    for (let i = 0; i < payload.track_sections.length; i++) {
      const sec = payload.track_sections[i] as Record<string, unknown>;
      const secId = String(sec.id || `sec[${i}]`);
      if (!isValidFiniteCoord(sec.start_coord) || !isValidFiniteCoord(sec.end_coord)) {
        throw new GeometryContractError(`TrackSection '${secId}' has non-finite start_coord or end_coord`, version);
      }
      const startKm = Number(sec.chainage_start_km);
      const endKm = Number(sec.chainage_end_km);
      if (!Number.isFinite(startKm) || !Number.isFinite(endKm) || startKm >= endKm) {
        throw new GeometryContractError(`TrackSection '${secId}' has invalid/reversed chainage: ${startKm} >= ${endKm}`, version);
      }
      if (sec.validation_status === "INVALID") {
        throw new GeometryContractError(`TrackSection '${secId}' is flagged as INVALID operational data`, version);
      }
    }
  }

  // 5. Signals validation: must have finite coordinates and valid track references
  if (Array.isArray(payload.signals)) {
    for (let i = 0; i < payload.signals.length; i++) {
      const sig = payload.signals[i] as Record<string, unknown>;
      const sigId = String(sig.id || `signal[${i}]`);
      const pos = sig.position || sig.coordinates;
      if (!isValidFiniteCoord(pos)) {
        throw new GeometryContractError(`Signal '${sigId}' has non-finite coordinates`, version);
      }
      const ref = sig.referenced_track_section_id || sig.referenced_block_id || sig.block_id;
      if (!ref || typeof ref !== 'string' || !ref.trim()) {
        throw new GeometryContractError(`Signal '${sigId}' has no valid track reference`, version);
      }
    }
  }

  // 6. Possessions validation: extent and Safety Boundary #6 (immutable locks on GRANTED/IN_PROGRESS)
  if (Array.isArray(payload.possessions)) {
    for (let i = 0; i < payload.possessions.length; i++) {
      const poss = payload.possessions[i] as Record<string, unknown>;
      const possId = String(poss.id || `possession[${i}]`);
      const startKm = Number(poss.chainage_start_km);
      const endKm = Number(poss.chainage_end_km);
      if (Number.isFinite(startKm) && Number.isFinite(endKm) && startKm >= endKm) {
        throw new GeometryContractError(`Possession '${possId}' has invalid extent: ${startKm} >= ${endKm}`, version);
      }
      const status = String(poss.status || "").toUpperCase();
      if ((status === "GRANTED" || status === "IN_PROGRESS") && !poss.is_locked) {
        throw new GeometryContractError(
          `Critical Safety Invariant Violation: Possession '${possId}' in status '${status}' must be visibly locked (is_locked: true) and immutable.`,
          version
        );
      }
    }
  }

  // When Demo mode is false, strictly enforce that any assets or conflicts have canonical coordinates
  if (!isDemo) {
    if (Array.isArray(payload.assets)) {
      for (let i = 0; i < payload.assets.length; i++) {
        const ast = payload.assets[i] as Record<string, unknown>;
        const astId = String(ast.asset_id || `asset[${i}]`);
        const pos = ast.position || ast.coordinates;
        if (!isValidFiniteCoord(pos)) {
          throw new GeometryContractError(
            `Asset '${astId}' is missing canonical 3D coordinates in non-demo mode. The frontend must never invent asset geometry.`,
            version
          );
        }
      }
    }

    if (Array.isArray(payload.conflicts)) {
      for (let i = 0; i < payload.conflicts.length; i++) {
        const conf = payload.conflicts[i] as Record<string, unknown>;
        const confId = String(conf.id || `conflict[${i}]`);
        const pos = conf.position || conf.coordinates;
        if (!isValidFiniteCoord(pos)) {
          throw new GeometryContractError(
            `Conflict '${confId}' is missing canonical 3D coordinates in non-demo mode. The frontend must never invent conflict geometry.`,
            version
          );
        }
      }
    }
  }

  return data as NetworkGeometryResponse;
}
