import assert from 'node:assert/strict';
import {chromium} from '../.toolchain/motion-review/node_modules/playwright/index.mjs';
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-webgl']});
try {
  const page=await browser.newPage({viewport:{width:1100,height:1400}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.goto('http://localhost:5173/preview/');await page.waitForFunction(()=>window.motionViewerReady&&!window.modelPreview.state.loading);
  assert.equal(await page.locator('#version').inputValue(),'teal-character');
  assert.equal((await page.evaluate(()=>window.modelPreview.state.clips)).length,5);
  await page.locator('#play').click();
  const report=await page.evaluate(async()=>{
    const THREE=await import('three');
    const {GLTFLoader}=await import('three/addons/loaders/GLTFLoader.js');
    const {createCharacterMotion,CHARACTER_CLIPS}=await import('./character-motion.js');
    const gltf=await new GLTFLoader().loadAsync('./models/teal-character.glb');
    const mixer=new THREE.AnimationMixer(gltf.scene);let seed=481;
    const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296};
    const motion=createCharacterMotion(mixer,gltf.animations,{random,minWait:.15,maxWait:.3});
    const history=[];let lastCount=0,maxWeightError=0,minY=Infinity,maxStep=0,previous=null,worstStep=null,elapsed=0;
    const tick=()=>{
      motion.update(1/60);const s=motion.state;
      maxWeightError=Math.max(maxWeightError,Math.abs(Object.values(s.weights).reduce((a,b)=>a+b,0)-1));
      gltf.scene.updateMatrixWorld(true);
      const points=[];
      gltf.scene.traverse(o=>{if(o.isSkinnedMesh){o.skeleton.update();
        for(let i=0;i<o.geometry.attributes.position.count;i++){
          const p=o.localToWorld(o.getVertexPosition(i,new THREE.Vector3()));points.push(p.x,p.y,p.z);minY=Math.min(minY,p.y);
        }}});
      if(!points.every(Number.isFinite))throw new Error('Non-finite deformed vertex');
      if(previous)for(let i=0;i<points.length;i++){const step=Math.abs(points[i]-previous[i]);if(step>maxStep){maxStep=step;worstStep={elapsed,state:s,coordinate:i};}}
      elapsed+=1/60;
      previous=points;
      if(s.accentCount!==lastCount){history.push(s.lastAccent);lastCount=s.accentCount;}
    };
    const run=seconds=>{for(let i=0;i<Math.ceil(seconds*60);i++)tick()};
    run(24);
    if(history.length<4||history.some((n,i)=>i&&n===history[i-1]))throw new Error('Idle scheduler repetition');
    // Interrupt whichever accent/transition is active, then hold walking.
    motion.setMoving(true);if(motion.state.target!=='Walk'||motion.state.accent)throw new Error('Walking priority');
    run(.45);if(motion.state.weights.Walk!==1)throw new Error('Walk did not finish blending');
    const count=motion.state.accentCount;run(12);
    if(motion.state.accentCount!==count)throw new Error('Accent ran during walking');
    for(let i=0;i<12;i++){motion.setMoving(i%2===0);run(.08)}
    motion.setMoving(false);run(.5);
    for(const name of CHARACTER_CLIPS.accents){
      // Clear any auto accent by briefly selecting walk and idle, with long wait.
      motion.dispose();
      const isolated=createCharacterMotion(mixer,gltf.animations,{minWait:100,maxWait:100});
      if(!isolated.playAccent(name))throw new Error('Could not trigger '+name);
      for(let i=0;i<260;i++)isolated.update(1/60);
      if(isolated.state.target!==CHARACTER_CLIPS.idle||isolated.state.accent)throw new Error('Accent did not return to idle');
      isolated.dispose();
    }
    return {history,maxWeightError,minY,maxStep,worstStep};
  });
  assert(report.maxWeightError<1e-12);
  assert(report.minY>-.02,`Excessive floor penetration: ${report.minY}`);
  assert(report.maxStep<.09,`Visible one-frame pop: ${report.maxStep}`);
  await page.locator('#character-mode').selectOption('walk');
  await page.waitForFunction(()=>window.modelPreview.state.character.weights.Walk===1);
  await page.locator('#character-mode').selectOption('idle');
  await page.waitForFunction(()=>!window.modelPreview.state.character.transitioning);
  await page.locator('#idle-accent').click();
  await page.waitForFunction(()=>window.modelPreview.state.character.accent!==null);
  await page.locator('#character-mode').selectOption('walk');
  assert.equal(await page.evaluate(()=>window.modelPreview.state.character.accent),null);
  await page.locator('#character-mode').selectOption('inspect');
  const options=await page.locator('#clip option').evaluateAll(es=>es.map(e=>({name:e.textContent,value:e.value})));
  for(const clip of options){
    await page.locator('#clip').selectOption(clip.value);
    await page.locator('#time').evaluate(e=>{e.value=1.8;e.dispatchEvent(new Event('input'))});
    await page.waitForTimeout(80);
    await page.screenshot({path:`assets/teal-peasant/idle-set/review-${clip.name}.png`});
    assert.equal(await page.evaluate(()=>window.modelPreview.state.character),null);
  }
  await page.locator('#character-mode').selectOption('idle');
  await page.locator('#play').click();const paused=await page.evaluate(()=>window.modelPreview.state.character.time);
  await page.waitForTimeout(200);assert.equal(await page.evaluate(()=>window.modelPreview.state.character.time),paused);
  assert.deepEqual(errors,[]);
  const fs=await import('node:fs/promises');await fs.writeFile('assets/teal-peasant/idle-set/runtime-validation.json',JSON.stringify(report,null,2)+'\n');
  console.log('PASS: five clips, randomized accents without immediate repeats, walking priority, rapid reversals, return to idle, normalized blend weights, finite posed vertices, UI inspection and pause.',report);
} finally {await browser.close()}
