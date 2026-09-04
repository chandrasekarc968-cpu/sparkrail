import React, { useMemo, useRef, useEffect } from 'react';
import * as THREE from 'three';
import type { OHEMast, SignalMarker, AssetHealthRecord } from '../../api/types';
import type { SelectedEntity } from '../../hooks/usePlanningSimulation';

interface InstancedTrackAssetsProps {
  oheMasts: OHEMast[];
  signals?: SignalMarker[];
  assets?: AssetHealthRecord[];
  onSelectEntity?: (entity: SelectedEntity) => void;
  selectedId?: string;
  maxDistance?: number;
}

// Module-level shared reusable geometries to eliminate allocation thrashing
const mastPoleGeometry = new THREE.CylinderGeometry(0.2, 0.25, 5.5, 8);
const mastArmGeometry = new THREE.CylinderGeometry(0.1, 0.1, 2.4, 6);
const mastInsulatorGeometry = new THREE.CylinderGeometry(0.2, 0.15, 0.6, 8);

const signalPoleGeometry = new THREE.CylinderGeometry(0.12, 0.12, 3.8, 8);
const signalHeadGeometry = new THREE.BoxGeometry(0.5, 1.2, 0.4);

const assetPinGeometry = new THREE.CylinderGeometry(0.08, 0.08, 2.4, 8);
const assetSphereGeometry = new THREE.SphereGeometry(0.45, 10, 10);

// Module-level shared reusable materials
const mastMaterialNormal = new THREE.MeshStandardMaterial({ color: '#64748b', metalness: 0.7, roughness: 0.4 });
const mastArmMaterial = new THREE.MeshStandardMaterial({ color: '#475569', metalness: 0.8 });
const insulatorMaterial = new THREE.MeshStandardMaterial({ color: '#38bdf8', roughness: 0.2 });

const signalPoleMaterial = new THREE.MeshStandardMaterial({ color: '#334155', metalness: 0.6 });
const signalHeadMaterial = new THREE.MeshStandardMaterial({ color: '#0f172a' });

const assetHealthyMaterial = new THREE.MeshStandardMaterial({ color: '#10b981', roughness: 0.3 });
const assetMajorMaterial = new THREE.MeshStandardMaterial({ color: '#f59e0b', roughness: 0.3 });

export const InstancedTrackAssets: React.FC<InstancedTrackAssetsProps> = React.memo(({
  oheMasts,
  signals = [],
  assets = [],
  onSelectEntity
}) => {
  const poleMeshRef = useRef<THREE.InstancedMesh>(null);
  const armMeshRef = useRef<THREE.InstancedMesh>(null);
  const insulatorMeshRef = useRef<THREE.InstancedMesh>(null);

  const signalPoleRef = useRef<THREE.InstancedMesh>(null);
  const signalHeadRef = useRef<THREE.InstancedMesh>(null);

  const assetPinRef = useRef<THREE.InstancedMesh>(null);
  const assetSphereRef = useRef<THREE.InstancedMesh>(null);

  const dummy = useMemo(() => new THREE.Object3D(), []);

  // 1. Configure OHE Masts InstancedMesh transforms
  useEffect(() => {
    if (!poleMeshRef.current || !armMeshRef.current || !insulatorMeshRef.current) return;
    const count = oheMasts.length;
    if (count === 0) return;

    for (let i = 0; i < count; i++) {
      const mast = oheMasts[i];
      const pos = mast.position || mast.coordinates || { x: 0, y: 0, z: 0 };

      // Pole
      dummy.position.set(pos.x, pos.y + 2.75, pos.z);
      dummy.rotation.set(0, 0, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      poleMeshRef.current.setMatrixAt(i, dummy.matrix);

      // Horizontal Cantilever Arm
      dummy.position.set(pos.x, pos.y + 5.2, pos.z - 1.2);
      dummy.rotation.set(0, 0, Math.PI / 2);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      armMeshRef.current.setMatrixAt(i, dummy.matrix);

      // Insulator Bell
      dummy.position.set(pos.x, pos.y + 4.8, pos.z - 1.8);
      dummy.rotation.set(0, 0, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      insulatorMeshRef.current.setMatrixAt(i, dummy.matrix);
    }

    poleMeshRef.current.instanceMatrix.needsUpdate = true;
    armMeshRef.current.instanceMatrix.needsUpdate = true;
    insulatorMeshRef.current.instanceMatrix.needsUpdate = true;
  }, [oheMasts, dummy]);

  // 2. Configure Signals InstancedMesh transforms
  useEffect(() => {
    if (!signalPoleRef.current || !signalHeadRef.current) return;
    const count = signals.length;
    if (count === 0) return;

    for (let i = 0; i < count; i++) {
      const sig = signals[i];
      const pos = sig.position || sig.coordinates || { x: 0, y: 0, z: 0 };

      // Pole
      dummy.position.set(pos.x, pos.y + 1.9, pos.z);
      dummy.rotation.set(0, 0, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      signalPoleRef.current.setMatrixAt(i, dummy.matrix);

      // Signal Head Housing
      dummy.position.set(pos.x, pos.y + 3.4, pos.z);
      dummy.rotation.set(0, sig.direction === 'DOWN' ? Math.PI : 0, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      signalHeadRef.current.setMatrixAt(i, dummy.matrix);
    }

    signalPoleRef.current.instanceMatrix.needsUpdate = true;
    signalHeadRef.current.instanceMatrix.needsUpdate = true;
  }, [signals, dummy]);

  // 3. Configure Assets InstancedMesh transforms
  useEffect(() => {
    if (!assetPinRef.current || !assetSphereRef.current) return;
    const count = assets.length;
    if (count === 0) return;

    for (let i = 0; i < count; i++) {
      const ast = assets[i];
      const pos = ast.position || ast.coordinates;
      if (!pos) {
        dummy.position.set(0, -9999, 0);
        dummy.scale.set(0, 0, 0);
        dummy.updateMatrix();
        assetPinRef.current.setMatrixAt(i, dummy.matrix);
        assetSphereRef.current.setMatrixAt(i, dummy.matrix);
        continue;
      }

      // Pin
      dummy.position.set(pos.x, pos.y + 1.2, pos.z);
      dummy.rotation.set(0, 0, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      assetPinRef.current.setMatrixAt(i, dummy.matrix);

      // Inspection indicator sphere
      dummy.position.set(pos.x, pos.y + 2.5, pos.z);
      dummy.rotation.set(0, 0, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      assetSphereRef.current.setMatrixAt(i, dummy.matrix);
    }

    assetPinRef.current.instanceMatrix.needsUpdate = true;
    assetSphereRef.current.instanceMatrix.needsUpdate = true;
  }, [assets, dummy]);

  // Click handlers mapping instanceId back to entity
  const handleMastClick = (e: { stopPropagation: () => void; instanceId?: number }) => {
    e.stopPropagation();
    if (e.instanceId !== undefined && e.instanceId < oheMasts.length) {
      const mast = oheMasts[e.instanceId];
      onSelectEntity?.({ type: 'asset', id: mast.id, data: mast });
    }
  };

  const handleSignalClick = (e: { stopPropagation: () => void; instanceId?: number }) => {
    e.stopPropagation();
    if (e.instanceId !== undefined && e.instanceId < signals.length) {
      const sig = signals[e.instanceId];
      onSelectEntity?.({ type: 'asset', id: sig.id, data: sig });
    }
  };

  const handleAssetClick = (e: { stopPropagation: () => void; instanceId?: number }) => {
    e.stopPropagation();
    if (e.instanceId !== undefined && e.instanceId < assets.length) {
      const ast = assets[e.instanceId];
      onSelectEntity?.({ type: 'asset', id: ast.asset_id, data: ast });
    }
  };

  return (
    <group>
      {/* 1. OHE Masts Batched Instancing */}
      {oheMasts.length > 0 && (
        <group onClick={handleMastClick}>
          <instancedMesh
            ref={poleMeshRef}
            args={[mastPoleGeometry, mastMaterialNormal, oheMasts.length]}
          />
          <instancedMesh
            ref={armMeshRef}
            args={[mastArmGeometry, mastArmMaterial, oheMasts.length]}
          />
          <instancedMesh
            ref={insulatorMeshRef}
            args={[mastInsulatorGeometry, insulatorMaterial, oheMasts.length]}
          />
        </group>
      )}

      {/* 2. Track Signals Batched Instancing */}
      {signals.length > 0 && (
        <group onClick={handleSignalClick}>
          <instancedMesh
            ref={signalPoleRef}
            args={[signalPoleGeometry, signalPoleMaterial, signals.length]}
          />
          <instancedMesh
            ref={signalHeadRef}
            args={[signalHeadGeometry, signalHeadMaterial, signals.length]}
          />
        </group>
      )}

      {/* 3. Physical Asset Telemetry Markers Batched Instancing */}
      {assets.length > 0 && (
        <group onClick={handleAssetClick}>
          <instancedMesh
            ref={assetPinRef}
            args={[assetPinGeometry, assetHealthyMaterial, assets.length]}
          />
          <instancedMesh
            ref={assetSphereRef}
            args={[assetSphereGeometry, assetMajorMaterial, assets.length]}
          />
        </group>
      )}
    </group>
  );
});
