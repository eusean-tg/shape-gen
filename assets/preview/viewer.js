import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createClothingPalette } from './clothing-palette.js';
import { createCharacterMotion } from './character-motion.js';

// Shared by the reusable viewer and the older experiment review pages.
export function createViewer({ examples, baseURL = document.baseURI }) {
  const el = id => document.getElementById(id);
  const viewport = el('viewport');
  // GLB durations are floating-point seconds; fixed steps can make the exact
  // endpoint unreachable (for example 1.29999995 seconds with a .001 step).
  el('time').step = 'any';
  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#1b2632');
  const camera = new THREE.PerspectiveCamera(38, 1, .0001, 100);
  const renderer = new THREE.WebGLRenderer({ antialias: true, logarithmicDepthBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  viewport.appendChild(renderer.domElement);
  scene.add(new THREE.HemisphereLight(0xe1efff, 0x626052, 2.3));
  const key = new THREE.DirectionalLight(0xfff1d7, 3);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  scene.add(key, key.target);
  const fill = new THREE.DirectionalLight(0xb1d3ff, 1);
  fill.position.set(4, 3, -3);
  scene.add(fill);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(1, 1),
    new THREE.MeshStandardMaterial({ color: 0x586979, roughness: 1 }));
  const checker = document.createElement('canvas');
  checker.width = checker.height = 128;
  const context = checker.getContext('2d');
  context.fillStyle = '#536272'; context.fillRect(0, 0, 128, 128);
  context.fillStyle = '#657585'; context.fillRect(0, 0, 64, 64); context.fillRect(64, 64, 64, 64);
  const floorMap = new THREE.CanvasTexture(checker);
  floorMap.colorSpace = THREE.SRGBColorSpace;
  floorMap.wrapS = floorMap.wrapT = THREE.RepeatWrapping;
  floorMap.repeat.set(200, 200);
  floorMap.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  ground.material.color.set(0xffffff);
  ground.material.map = floorMap;
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
  let grid;
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.zoomToCursor = true;
  controls.maxPolarAngle = Math.PI * .499;
  let model, mixer, action, skeleton, root, clips = [], duration = 0;
  let playing = false, time = 0, scale = 1, loadId = 0, busy = false;
  let palette = null, paletteMask = null;
  let characterMotion = null, characterEnabled = false;
  function setCharacterMode(mode) {
    if (!characterEnabled) return;
    if (el('character-mode')) el('character-mode').value = mode;
    if (mode === 'inspect') {
      characterMotion?.dispose(); characterMotion = null;
      selectClip(Number(el('clip').value), 0);
      if (el('character-status')) el('character-status').textContent = 'Choose an animation below';
    } else {
      characterMotion ??= createCharacterMotion(mixer, clips);
      characterMotion.setMoving(mode === 'walk');
    }
    if (el('idle-accent')) el('idle-accent').disabled = mode !== 'idle';
    updateControls();
  }
  if (el('character-mode')) el('character-mode').onchange = () => { setCharacterMode(el('character-mode').value); setPlaying(true); };
  if (el('idle-accent')) el('idle-accent').onclick = () => characterMotion?.playAccent();
  function clearPalette() {
    palette?.dispose(); paletteMask?.dispose(); palette = paletteMask = null;
    if (el('clothing-colors')) el('clothing-colors').hidden = true;
  }
  function showPalette() {
    if (!el('clothing-colors')) return;
    el('clothing-colors').hidden = !palette;
    if (!palette) return;
    el('clothing-inputs').replaceChildren(...palette.slots.map(slot => {
      const label = document.createElement('label'), input = document.createElement('input');
      input.type = 'color'; input.id = `color-${slot.key}`; input.value = slot.defaultColor;
      input.oninput = () => palette.setColor(slot.key, input.value);
      label.append(`${slot.label} `, input); return label;
    }));
    el('clothing-reset').onclick = () => { palette.reset(); showPalette(); };
  }
  const lastRoot = new THREE.Vector3();
  const loader = new GLTFLoader();
  const position = () => root ? root.getWorldPosition(new THREE.Vector3()) : new THREE.Vector3();
  const bounds = () => new THREE.Box3().setFromObject(model, true);
  const status = message => { el('status').textContent = message; };
  try { el('loop').checked = localStorage.getItem('shape-gen-loop') !== 'false'; } catch {}
  el('loop').onchange = () => {
    try { localStorage.setItem('shape-gen-loop', String(el('loop').checked)); } catch {}
  };
  function setPlaying(value) {
    playing = Boolean(value && action && duration > 0 && !busy);
    el('play').textContent = playing ? 'Pause' : 'Play';
  }
  function updateControls() {
    for (const id of ['play', 'restart', 'time', 'speed']) el(id).disabled = busy || !action || duration <= 0;
    el('clip').disabled = busy || !clips.length;
    el('skeleton').disabled = !skeleton;
    el('reset').disabled = !model;
    el('time').disabled ||= Boolean(characterMotion);
    el('loop').disabled = Boolean(characterMotion);
  }
  function poseAt(t) {
    if (!action) return;
    time = THREE.MathUtils.clamp(t, 0, duration);
    // Reset the action before seeking so a previously finished LoopOnce can replay.
    action.reset().setLoop(THREE.LoopOnce, 1);
    action.clampWhenFinished = true;
    action.play();
    mixer.setTime(time);
    model.updateMatrixWorld(true);
    const current = position();
    if (el('follow').checked) {
      const delta = current.clone().sub(lastRoot);
      controls.target.add(delta);
      camera.position.add(delta);
    }
    lastRoot.copy(current);
    el('time').value = time;
    el('timestamp').textContent = `${time.toFixed(2)} / ${duration.toFixed(2)} s`;
  }
  function resetView() {
    if (!model) return;
    const box = bounds();
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const radius = Math.max(size.length() / 2, scale * .01);
    const halfFov = Math.min(THREE.MathUtils.degToRad(camera.fov / 2),
      Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.aspect));
    const distance = radius / Math.sin(halfFov) * 1.12;
    controls.target.copy(center);
    camera.position.copy(center).add(new THREE.Vector3(-.55, .25, 1).normalize().multiplyScalar(distance));
    controls.update();
    lastRoot.copy(position());
  }
  function applyDisplay() {
    if (skeleton) skeleton.visible = el('skeleton').checked;
    model?.traverse(o => {
      if (o.isMesh) for (const m of [].concat(o.material)) m.wireframe = el('wire').checked;
    });
  }
  function disposeModel(object) {
    const geometries = new Set(), materials = new Set(), textures = new Set(), skeletons = new Set();
    object.traverse(o => {
      if (o.geometry) geometries.add(o.geometry);
      if (o.skeleton) skeletons.add(o.skeleton);
      for (const m of o.material ? [].concat(o.material) : []) {
        materials.add(m);
        for (const value of Object.values(m)) if (value?.isTexture) textures.add(value);
      }
    });
    for (const t of textures) { t.dispose(); t.source?.data?.close?.(); }
    for (const item of [...geometries, ...materials, ...skeletons]) item.dispose();
  }
  function chooseRoot() {
    // Follow a top-level animated bone/node, independent of skeleton naming.
    const candidates = [];
    for (const track of action?.getClip().tracks || []) {
      const binding = THREE.PropertyBinding.parseTrackName(track.name);
      if (binding.propertyName !== 'position') continue;
      const node = THREE.PropertyBinding.findNode(model, binding.nodeName);
      if (node) candidates.push(node);
    }
    let firstBone;
    model.traverse(o => { if (o.isBone && !firstBone) firstBone = o; });
    root = candidates.find(n => !candidates.some(other => {
      for (let parent = n.parent; parent; parent = parent.parent) if (parent === other) return true;
      return false;
    })) || firstBone || model;
    lastRoot.copy(position());
  }
  function selectClip(index, startTime = 0) {
    mixer.stopAllAction();
    action = clips[index] ? mixer.clipAction(clips[index]) : null;
    action?.setEffectiveWeight(1).setEffectiveTimeScale(1);
    duration = action ? action.getClip().duration : 0;
    time = 0;
    el('time').max = duration || 1;
    el('time').value = 0;
    el('timestamp').textContent = 'Static model';
    chooseRoot();
    if (action) poseAt(startTime);
    updateControls();
  }
  function configureStage(floorY) {
    const box = bounds();
    scale = Math.max(box.getSize(new THREE.Vector3()).length(), 1e-6);
    // Tiny model-relative near plane plus proximity adjustment for close inspection.
    camera.near = scale * .00001;
    camera.far = scale * 150;
    camera.updateProjectionMatrix();
    controls.minDistance = scale * .0001;
    controls.maxDistance = scale * 40;
    const center = box.getCenter(new THREE.Vector3());
    ground.scale.setScalar(scale * 100);
    ground.position.set(center.x, (floorY ?? box.min.y) - scale * .003, center.z);
    if (grid) { scene.remove(grid); grid.geometry.dispose(); grid.material.dispose(); }
    grid = new THREE.GridHelper(scale * 100, 200, 0x7594aa, 0x3c5162);
    grid.position.copy(ground.position).y += scale * .001;
    scene.add(grid);
    Object.assign(key.shadow.camera, { left: -scale * 2, right: scale * 2,
      top: scale * 2, bottom: -scale * 2, near: scale * .01, far: scale * 15 });
    key.shadow.camera.updateProjectionMatrix();
    key.shadow.normalBias = scale * .005;
    resetView();
  }
  async function load(source, label, { preserveTime = false, floorY, note = '', blend, clothing, character = false } = {}) {
    const id = ++loadId;
    const oldTime = time, wasPlaying = model ? playing : true;
    busy = true;
    setPlaying(false);
    updateControls();
    window.motionViewerReady = false;
    status(`Loading ${label}…`);
    let gltf, incomingMask;
    try {
      gltf = source instanceof File
        ? await loader.parseAsync(await source.arrayBuffer(), '')
        : await loader.loadAsync(new URL(source, baseURL).href);
      if (id !== loadId) { disposeModel(gltf.scene); return; }
      const box = new THREE.Box3().setFromObject(gltf.scene, true);
      if (box.isEmpty() || !Number.isFinite(box.min.length() + box.max.length())) {
        disposeModel(gltf.scene);
        throw new Error('No visible mesh found in this GLB.');
      }
      let paletteConfig;
      if (clothing) {
        const response = await fetch(new URL(clothing.config, baseURL));
        if (!response.ok) throw new Error('Could not load clothing palette');
        paletteConfig = await response.json();
        incomingMask = await new THREE.TextureLoader().loadAsync(new URL(clothing.mask, baseURL).href);
        if (id !== loadId) { incomingMask.dispose(); disposeModel(gltf.scene); return; }
      }
      clearPalette();
      characterMotion?.dispose(); characterMotion = null;
      characterEnabled = character;
      if (el('character-playback')) el('character-playback').hidden = !character;
      if (model) {
        mixer.stopAllAction(); mixer.uncacheRoot(model);
        scene.remove(model); disposeModel(model);
        if (skeleton) { scene.remove(skeleton); skeleton.dispose(); }
      }
      model = gltf.scene;
      if (incomingMask) {
        paletteMask = incomingMask;
        palette = createClothingPalette(model, paletteMask, paletteConfig);
      }
      showPalette();
      model.traverse(o => {
        if (o.isMesh) {
          o.castShadow = true; o.receiveShadow = true;
          // Animated vertices can leave the cached rest-pose bounds. At close range,
          // stale bounds made the entire character disappear despite being in view.
          if (o.isSkinnedMesh || o.morphTargetInfluences) o.frustumCulled = false;
        }
      });
      scene.add(model);
      clips = gltf.animations;
      mixer = new THREE.AnimationMixer(model);
      el('clip').replaceChildren(...(clips.length ? clips.map((clip, i) => new Option(clip.name || `Clip ${i + 1}`, i))
        : [new Option('No animation', '')]));
      let hasBones = false;
      model.traverse(o => { if (o.isBone) hasBones = true; });
      skeleton = hasBones ? new THREE.SkeletonHelper(model) : null;
      if (skeleton) { skeleton.material.depthTest = false; skeleton.renderOrder = 10; scene.add(skeleton); }
      busy = false;
      const firstClip = characterEnabled ? Math.max(0, clips.findIndex(c => c.name === 'Idle_Breathe')) : 0;
      el('clip').value = String(firstClip);
      selectClip(firstClip, preserveTime ? oldTime : 0);
      if (characterEnabled) setCharacterMode('idle');
      configureStage(floorY);
      applyDisplay();
      setPlaying(preserveTime ? wasPlaying : true);
      status(`${label} · ${clips.length ? `${clips.length} animation${clips.length === 1 ? '' : 's'}` : 'static model'}`);
      if (el('asset-note')) el('asset-note').textContent = note;
      if (el('asset-source')) {
        el('asset-source').hidden = !blend;
        if (blend) el('asset-source').href = new URL(blend, baseURL).href;
      }
      window.motionViewerReady = true;
    } catch (error) {
      if (gltf && gltf.scene !== model) { incomingMask?.dispose(); disposeModel(gltf.scene); }
      if (id !== loadId) return;
      busy = false;
      updateControls();
      setPlaying(wasPlaying);
      status(`Could not load ${label}: ${error.message}`);
      window.motionViewerReady = Boolean(model);
    }
  }
  el('version').replaceChildren(...examples.map(item => new Option(item.label, item.id)));
  const loadExample = preserveTime => {
    const example = examples.find(item => item.id === el('version').value);
    if (example) return load(example.src, example.label, {
      preserveTime, floorY: example.floorY, note: example.note, blend: example.blend, clothing: example.clothing, character: example.character
    });
  };
  el('version').onchange = () => loadExample(true);
  el('clip').onchange = () => { if (characterMotion) setCharacterMode('inspect'); selectClip(Number(el('clip').value)); resetView(); setPlaying(true); };
  el('play').onclick = () => { if (!characterMotion && time >= duration) poseAt(0); setPlaying(!playing); };
  el('restart').onclick = () => {
    if (characterMotion) {
      const mode=characterMotion.state.mode; characterMotion.dispose(); characterMotion=null; setCharacterMode(mode);
    } else poseAt(0);
    setPlaying(true);
  };
  el('time').oninput = () => { setPlaying(false); poseAt(Number(el('time').value)); };
  el('skeleton').onchange = applyDisplay;
  el('wire').onchange = applyDisplay;
  el('reset').onclick = resetView;
  async function openFile(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.glb')) { status('Choose a .glb with its textures and animation clips embedded.'); return; }
    el('version').value = '';
    await load(file, file.name);
  }
  if (el('file')) el('file').onchange = async () => {
    await openFile(el('file').files[0]); el('file').value = '';
  };
  viewport.addEventListener('dragover', event => { event.preventDefault(); viewport.classList.add('dragging'); });
  viewport.addEventListener('dragleave', () => viewport.classList.remove('dragging'));
  viewport.addEventListener('drop', event => {
    event.preventDefault(); viewport.classList.remove('dragging'); openFile(event.dataTransfer.files[0]);
  });
  new ResizeObserver(() => {
    camera.aspect = viewport.clientWidth / viewport.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(viewport.clientWidth, viewport.clientHeight, false);
  }).observe(viewport);
  let previous = performance.now(), loopCount = 0;
  renderer.setAnimationLoop(now => {
    const delta = Math.min((now - previous) / 1000, .1); previous = now;
    if (playing && action) {
      if (characterMotion) {
        const before=characterMotion.state;
        characterMotion.update(delta * Number(el('speed').value));
        const state=characterMotion.state;
        if (state.target===before.target && state.time<before.time) loopCount++;
        time=state.time;duration=state.duration;el('time').max=duration;el('time').value=time;
        el('timestamp').textContent=`${time.toFixed(2)} / ${duration.toFixed(2)} s`;
        if (el('character-status')) el('character-status').textContent=state.target.replaceAll('_',' ') + (state.transitioning ? ' · blending' : '');
        model.updateMatrixWorld(true);
        const current=position();
        if (el('follow').checked) { const delta=current.clone().sub(lastRoot); controls.target.add(delta); camera.position.add(delta); }
        lastRoot.copy(current);
      } else {
      let next = time + delta * Number(el('speed').value);
      if (next >= duration && el('loop').checked) { next %= duration; loopCount++; }
      poseAt(next);
      if (time >= duration) setPlaying(false);
      }
    }
    const p = position();
    key.position.copy(p).add(new THREE.Vector3(-1.5, 3, 2).multiplyScalar(scale));
    key.target.position.copy(p);
    controls.update();
    const near = Math.max(scale * 1e-8, Math.min(scale * 1e-5, camera.position.distanceTo(controls.target) * .001));
    if (camera.near !== near) { camera.near = near; camera.updateProjectionMatrix(); }
    renderer.render(scene, camera);
  });
  // Expose the viewer for console inspection and real-browser smoke tests.
  window.modelPreview = { camera, controls, renderer, scene,
    get state() { return { time, duration, playing, loopCount, scale, clips: clips.map(c => c.name), loading: busy, character: characterMotion?.state ?? null }; } };
  loadExample(false);
}
