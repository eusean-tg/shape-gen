import assert from 'node:assert/strict';
import { chromium } from '../.toolchain/motion-review/node_modules/playwright/index.mjs';
const browser = await chromium.launch({headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-webgl']});
try {
  const page = await browser.newPage({viewport:{width:1100,height:1100}}), errors=[];
  page.on('pageerror', e=>errors.push(e.message));
  page.on('console', m=>{if(m.type()==='error')errors.push(m.text());});
  const ready=()=>page.waitForFunction(()=>window.motionViewerReady&&!window.modelPreview.state.loading);
  await page.goto('http://localhost:5173/preview/'); await ready();
  await page.locator('#version').selectOption('teal-rest'); await ready();
  assert(await page.locator('#clothing-colors').isVisible());
  assert.equal(await page.locator('#clothing-inputs input').count(),6);
  await page.evaluate(()=>{const v=window.modelPreview;v.controls.enableDamping=false;v.controls.target.set(0,1,0);v.camera.position.set(0,1.25,3.6);v.controls.update()});
  // Compare actual rendered pixels and project known rest-surface samples.
  const sample=()=>page.evaluate(async()=>{
    const THREE=await import('three'), v=window.modelPreview;
    v.renderer.render(v.scene,v.camera);
    const gl=v.renderer.getContext(), w=gl.drawingBufferWidth,h=gl.drawingBufferHeight;
    const patch=(x,y,z)=>{const p=new THREE.Vector3(x,y,z).project(v.camera),data=new Uint8Array(9*9*4);
      gl.readPixels(Math.round((p.x+1)*w/2)-4,Math.round((p.y+1)*h/2)-4,9,9,gl.RGBA,gl.UNSIGNED_BYTE,data);return [...data]};
    const all=new Uint8Array(w*h*4);gl.readPixels(0,0,w,h,gl.RGBA,gl.UNSIGNED_BYTE,all);
    let hash=2166136261;for(const value of all)hash=Math.imul(hash^value,16777619);
    return {hash,skin:patch(0,1.80,.09),hair:patch(0,1.94,.04),pants:patch(.1,.66,.09),tunic:patch(0,1.25,.12)};
  });
  const original=await sample();
  await page.locator('#color-tunic').evaluate(e=>{e.value='#d12f26';e.dispatchEvent(new Event('input'))});
  const red=await sample();
  assert.notEqual(red.hash,original.hash);
  assert.notDeepEqual(red.tunic,original.tunic,'Tunic visibly recolors');
  assert.deepEqual(red.skin,original.skin,'Face color remains unchanged');
  assert.deepEqual(red.hair,original.hair,'Hair color remains unchanged');
  assert.deepEqual(red.pants,original.pants,'Trousers independent of tunic');
  await page.locator('#color-trousers').evaluate(e=>{e.value='#e6c773';e.dispatchEvent(new Event('input'))});
  const gold=await sample();assert.notDeepEqual(gold.pants,red.pants);assert.deepEqual(gold.tunic,red.tunic);
  await page.screenshot({path:'assets/teal-peasant/collar-fix/clothing-colors.png'});
  await page.locator('#clothing-reset').click();assert.equal((await sample()).hash,original.hash,'Reset restores exact rendered colors');
  await page.locator('#version').selectOption('walk-cycle');await ready();assert(await page.locator('#clothing-colors').isHidden());
  await page.locator('#version').selectOption('teal-walk');await ready();assert(await page.locator('#clothing-colors').isVisible());
  await page.locator('#restart').click();await page.waitForFunction(()=>window.modelPreview.state.loopCount>=1);
  assert.deepEqual(errors,[]);
  console.log('PASS: actual rendered recoloring, independent tunic/trousers, protected skin/hair, exact reset, variant switching and animation.');
} finally {await browser.close();}
