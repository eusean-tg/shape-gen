import * as THREE from 'three';

export const CHARACTER_CLIPS = {
  idle: 'Idle_Breathe', walk: 'Walk',
  accents: ['Idle_LookAround', 'Idle_WeightShift', 'Idle_HandCheck']
};

// Pass the same mixer/model that owns the clips. Call update(deltaSeconds) once
// per rendered frame; elapsed simulation time controls the idle scheduler.
export function createCharacterMotion(mixer, clips, {
  random = Math.random, minWait = 6, maxWait = 12, fadeSeconds = .4, groundTransitions = true
} = {}) {
  const names = [CHARACTER_CLIPS.idle, CHARACTER_CLIPS.walk, ...CHARACTER_CLIPS.accents];
  const actions = new Map();
  for (const name of names) {
    const clip = clips.find(c => c.name === name);
    if (!clip) throw new Error(`Missing character clip: ${name}`);
    actions.set(name, mixer.clipAction(clip));
  }
  mixer.stopAllAction();
  const model=mixer.getRoot(), baseY=model.position.y, soleSamples=[];
  let groundLift=0;
  // Candidate sole vertices in this character's Y-up rest geometry. Only sample
  // during blends; stable authored clips retain their own contact correction.
  const meshes=[];let low=Infinity,high=-Infinity;
  model.traverse(o=>{if(o.isSkinnedMesh){meshes.push(o);const p=o.geometry.attributes.position;
    for(let i=0;i<p.count;i++){low=Math.min(low,p.getY(i));high=Math.max(high,p.getY(i));}}});
  for(const mesh of meshes){const p=mesh.geometry.attributes.position;
    for(let i=0;i<p.count;i++)if(p.getY(i)<low+(high-low)*.08)soleSamples.push([mesh,i]);}
  const point=new THREE.Vector3();
  let mode = 'idle', target = CHARACTER_CLIPS.idle, lastAccent = null, accent = null;
  let wait = delay(), transition = null, accentCount = 0, transitionCount = 0;
  const weights = Object.fromEntries(names.map(n => [n, n === target ? 1 : 0]));
  for (const [name, action] of actions) {
    action.reset().setEffectiveWeight(weights[name]);
    action.setLoop(CHARACTER_CLIPS.accents.includes(name) ? THREE.LoopOnce : THREE.LoopRepeat, Infinity);
    action.clampWhenFinished = CHARACTER_CLIPS.accents.includes(name);
    action.play();
  }
  function delay() { return minWait + random() * (maxWait - minWait); }
  function change(name) {
    if (target === name) return;
    const action = actions.get(name);
    // Reversing a fade must keep a still-visible walk's phase. Rewinding that
    // action while it has weight causes a pose pop on rapid start/stop input.
    if (name !== CHARACTER_CLIPS.idle && weights[name] < 1e-6) action.reset().play();
    action.enabled = true;
    transition = { from: { ...weights }, elapsed: 0 };
    target = name; transitionCount++;
  }
  function playAccent(name) {
    if (mode !== 'idle' || accent || transition) return false;
    const choices = CHARACTER_CLIPS.accents.filter(n => n !== lastAccent);
    name ??= choices[Math.min(choices.length - 1, Math.floor(random() * choices.length))];
    if (!CHARACTER_CLIPS.accents.includes(name)) throw new Error(`Unknown idle accent: ${name}`);
    accent = lastAccent = name; accentCount++; change(name); return true;
  }
  return {
    setMoving(moving) {
      const next = moving ? 'walk' : 'idle';
      if (mode === next) return;
      mode = next; accent = null; wait = delay();
      change(moving ? CHARACTER_CLIPS.walk : CHARACTER_CLIPS.idle);
    },
    playAccent,
    update(delta) {
      if (!Number.isFinite(delta) || delta <= 0) return;
      const wasBlending=Boolean(transition);
      if (transition) {
        transition.elapsed += delta;
        const t = Math.min(1, transition.elapsed / fadeSeconds);
        const blend = t*t*(3-2*t);
        for (const name of names) weights[name] = THREE.MathUtils.lerp(transition.from[name], name === target ? 1 : 0, blend);
        if (t === 1) transition = null;
      }
      for (const [name, action] of actions) action.setEffectiveWeight(weights[name]);
      mixer.update(delta);
      model.position.y=baseY;groundLift=0;model.updateMatrixWorld(true);
      if(groundTransitions && wasBlending && soleSamples.length){
        for(const mesh of meshes)mesh.skeleton.update();
        let minimum=Infinity;
        for(const [mesh,index] of soleSamples){
          mesh.getVertexPosition(index,point);mesh.localToWorld(point);model.worldToLocal(point);
          minimum=Math.min(minimum,point.y);
        }
        groundLift=Math.max(0,.001-minimum);model.position.y=baseY+groundLift;model.updateMatrixWorld(true);
      }
      if (mode === 'idle') {
        if (accent) {
          const action = actions.get(accent);
          if (action.time >= action.getClip().duration - fadeSeconds) {
            accent = null; wait = delay(); change(CHARACTER_CLIPS.idle);
          }
        } else if (!transition) {
          wait -= delta;
          if (wait <= 0) playAccent();
        }
      }
    },
    get state() {
      const action = actions.get(target);
      return { mode, target, accent, lastAccent, nextAccentIn: wait,
        weights: { ...weights }, transitioning: Boolean(transition), accentCount, transitionCount,
        time: action.time, duration: action.getClip().duration, groundLift };
    },
    dispose() { for (const action of actions.values()) action.stop(); model.position.y=baseY; }
  };
}
