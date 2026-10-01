// Copy this file and clothing-palette.js into your React Three Fiber project.
import { useEffect, useMemo, useRef } from 'react';
import { useGLTF, useTexture } from '@react-three/drei';
import { useThree, useFrame } from '@react-three/fiber';
import { AnimationMixer } from 'three';
import { clone } from 'three/addons/utils/SkeletonUtils.js';
import { createClothingPalette } from './clothing-palette.js';
import { createCharacterMotion } from './character-motion.js';

export function TealPeasant({ config, colors = {}, moving = false, url = '/teal/teal-character.glb',
  maskUrl = '/teal/clothing-mask.png', ...props }) {
  const { scene, animations } = useGLTF(url);
  const mask = useTexture(maskUrl);
  const model = useMemo(() => clone(scene), [scene]);
  const palette = useRef();
  const invalidate = useThree(state => state.invalidate);
  const mixer = useMemo(() => new AnimationMixer(model), [model]);
  const motion = useRef();
  useEffect(() => {
    palette.current = createClothingPalette(model, mask, config);
    return () => { palette.current.dispose(); palette.current = null; };
  }, [model, mask, config]);
  useEffect(() => {
    palette.current.reset();
    for (const [key, value] of Object.entries(colors)) palette.current.setColor(key, value);
    invalidate();
  }, [colors, model, mask, config, invalidate]);
  useEffect(() => {
    motion.current = createCharacterMotion(mixer, animations);
    return () => { motion.current.dispose(); motion.current = null; mixer.uncacheRoot(model); };
  }, [mixer, animations, model]);
  useEffect(() => { motion.current.setMoving(moving); }, [moving, mixer, animations, model]);
  useFrame((_, delta) => motion.current?.update(Math.min(delta, .1)));
  // Shared loader geometry/textures remain cached; the helper owns cloned materials.
  return <group {...props}><primitive object={model} dispose={null} /></group>;
}
