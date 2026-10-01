import * as THREE from 'three';

// For Three.js WebGLRenderer / React Three Fiber's default WebGL renderer.
// mask: UV-aligned region IDs 0 (keep original) and 1..6 (palette slots).
// Clone the skinned scene per character before calling this helper.
export function createClothingPalette(model, mask, config) {
  if (config.version !== 1 || config.slots.length !== 6) throw new Error('Unsupported clothing palette');
  mask.colorSpace = THREE.NoColorSpace;
  mask.flipY = false;
  mask.minFilter = mask.magFilter = THREE.NearestFilter;
  mask.generateMipmaps = false;
  mask.needsUpdate = true;
  const ratios = config.slots.map(() => new THREE.Vector3(1, 1, 1));
  const originals = new Map(), materials = new Map();
  model.traverse(object => {
    if (!object.isMesh) return;
    originals.set(object, object.material);
    const prepare = source => {
      if (materials.has(source)) return materials.get(source);
      if (!source.isMeshStandardMaterial || !source.map) return source;
      const material = source.clone();
      material.onBeforeCompile = shader => {
        shader.uniforms.uClothingMask = { value: mask };
        shader.uniforms.uClothingRatios = { value: ratios };
        shader.fragmentShader = `uniform sampler2D uClothingMask;
uniform vec3 uClothingRatios[6];\n` + shader.fragmentShader;
        shader.fragmentShader = shader.fragmentShader.replace('#include <map_fragment>', `
#include <map_fragment>
#ifdef USE_MAP
  float clothingRegion = floor(texture2D(uClothingMask, vMapUv).r * 255.0 + 0.5);
  for (int regionIndex = 0; regionIndex < 6; regionIndex++) {
    if (abs(clothingRegion - float(regionIndex + 1)) < 0.5)
      diffuseColor.rgb *= uClothingRatios[regionIndex];
  }
#endif`);
      };
      material.customProgramCacheKey = () => 'shape-gen-clothing-palette-v1';
      materials.set(source, material);
      return material;
    };
    object.material = Array.isArray(object.material) ? object.material.map(prepare) : prepare(object.material);
  });
  return {
    slots: config.slots,
    setColor(key, color) {
      const index = config.slots.findIndex(slot => slot.key === key);
      if (index < 0) throw new Error(`Unknown clothing region: ${key}`);
      const next = new THREE.Color(color);
      const base = new THREE.Color().setRGB(...config.slots[index].baseSRGB, THREE.SRGBColorSpace);
      ratios[index].set(next.r / base.r, next.g / base.g, next.b / base.b);
    },
    reset() { for (const value of ratios) value.set(1, 1, 1); },
    dispose() {
      for (const [object, material] of originals) object.material = material;
      for (const material of materials.values()) material.dispose();
      // The caller owns the mask texture and source materials.
    }
  };
}
