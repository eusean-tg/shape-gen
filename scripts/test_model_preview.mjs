// Run against the local preview server: node scripts/test_model_preview.mjs
import assert from 'node:assert/strict';
import { chromium } from '../.toolchain/motion-review/node_modules/playwright/index.mjs';

// A real, self-contained cube GLB with two node animations and no skeleton.
// Meter, millimeter and kilometer-scale fixtures exercise generic loading/framing.
function cubeGLB(size) {
  const positions = new Float32Array([-1,-1,-1, 1,-1,-1, 1,1,-1, -1,1,-1, -1,-1,1, 1,-1,1, 1,1,1, -1,1,1].map(v=>v*size/2));
  const indices = new Uint16Array([0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,3,7,6,3,6,2,0,4,7,0,7,3,1,2,6,1,6,5]);
  const arrays=[positions,indices,new Float32Array([0,1]),new Float32Array([0,0,0,size,0,0]),new Float32Array([0,0,0,0,size,0])];
  let offset=0;
  const views=arrays.map(a=>{const v={buffer:0,byteOffset:offset,byteLength:a.byteLength};offset+=a.byteLength;return v});
  const doc={asset:{version:'2.0'},scene:0,scenes:[{nodes:[0]}],nodes:[{name:'TestCube',mesh:0}],
    meshes:[{primitives:[{attributes:{POSITION:0},indices:1,material:0}]}],
    materials:[{pbrMetallicRoughness:{baseColorFactor:[.2,.65,.9,1],metallicFactor:0,roughnessFactor:1}}],
    buffers:[{byteLength:offset}],bufferViews:views,
    accessors:[{bufferView:0,componentType:5126,count:8,type:'VEC3',min:[-size/2,-size/2,-size/2],max:[size/2,size/2,size/2]},
      {bufferView:1,componentType:5123,count:36,type:'SCALAR'},
      {bufferView:2,componentType:5126,count:2,type:'SCALAR',min:[0],max:[1]},
      {bufferView:3,componentType:5126,count:2,type:'VEC3'},
      {bufferView:4,componentType:5126,count:2,type:'VEC3'}],
    animations:['Move sideways','Move upwards'].map((name,i)=>({name,samplers:[{input:2,output:3+i,interpolation:'LINEAR'}],channels:[{sampler:0,target:{node:0,path:'translation'}}]}))};
  let json=Buffer.from(JSON.stringify(doc));
  json=Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,0x20)]);
  const bin=Buffer.concat(arrays.map(a=>Buffer.from(a.buffer)));
  const header=Buffer.alloc(12),jh=Buffer.alloc(8),bh=Buffer.alloc(8);
  header.writeUInt32LE(0x46546c67);header.writeUInt32LE(2,4);header.writeUInt32LE(28+json.length+bin.length,8);
  jh.writeUInt32LE(json.length);jh.writeUInt32LE(0x4e4f534a,4);bh.writeUInt32LE(bin.length);bh.writeUInt32LE(0x004e4942,4);
  return Buffer.concat([header,jh,json,bh,bin]);
}
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-webgl']});
const errors=[];
const base=process.env.PREVIEW_URL || 'http://localhost:5173';
try {
 const page=await browser.newPage({viewport:{width:1400,height:1080}});
 page.on('pageerror',e=>errors.push(e.message));
 const ready=()=>page.waitForFunction(()=>window.motionViewerReady && !window.modelPreview.state.loading);
 const state=()=>page.evaluate(()=>window.modelPreview.state);
 const seek=t=>page.locator('#time').evaluate((e,t)=>{e.value=t;e.dispatchEvent(new Event('input'))},t);
 await page.goto(base+'/preview/');await ready();
 await page.locator('#version').selectOption('masked');await ready();
 assert(await page.locator('#loop').isChecked());
 await seek(1.5);
 await page.locator('#version').selectOption('flat');await ready();
 assert.equal((await state()).time,1.5);assert.equal((await state()).playing,false);
 await page.locator('#version').selectOption('masked');await ready();
 await page.screenshot({path:'/tmp/model-preview.png'});
 await page.locator('#skeleton').check();await page.locator('#wire').check();
 await page.locator('#skeleton').uncheck();await page.locator('#wire').uncheck();
 const end=(await state()).duration;
 await seek(end-.1);await page.locator('#play').click();
 await page.waitForFunction(()=>window.modelPreview.state.loopCount>=1);
 assert((await state()).playing);
 await seek(end-.1);await page.locator('#play').click();
 await page.waitForFunction(()=>window.modelPreview.state.loopCount>=2);
 assert((await state()).playing);
 await page.locator('#loop').uncheck();await seek(end-.1);await page.locator('#play').click();
 await page.waitForFunction(()=>!window.modelPreview.state.playing);
 assert.equal((await state()).time,end);
 await page.locator('#restart').click();
 await page.waitForFunction(()=>window.modelPreview.state.time>0 && window.modelPreview.state.time<1);
 await page.locator('#loop').check();
 await seek(0);
 // Inspect the actual face from close range and verify the camera near plane.
 await page.evaluate(()=>{
   const v=window.modelPreview;
   const bone=v.scene.getObjectByName('head');
   if(!bone)throw new Error('Expected head in peasant fixture');
   const p=bone.getWorldPosition(v.controls.target.clone());
   v.controls.target.copy(p);v.camera.position.copy(p).add({x:-.22,y:.04,z:.42});v.controls.update();
 });
 await page.waitForTimeout(200);
 assert(await page.evaluate(()=>window.modelPreview.camera.near < .0001));
 // Compare actual center pixels with/without the character, catching the stale
 // animated-bounds culling bug that a near-plane assertion alone cannot detect.
 assert(await page.evaluate(()=>{
   const v=window.modelPreview, gl=v.renderer.getContext();
   let model=v.scene.getObjectByName('head');
   while(model.parent!==v.scene)model=model.parent;
   const sample=()=>{v.renderer.render(v.scene,v.camera);const pixel=new Uint8Array(4);
     gl.readPixels(gl.drawingBufferWidth/2|0,gl.drawingBufferHeight/2|0,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);return pixel};
   const visible=sample();model.visible=false;const hidden=sample();model.visible=true;sample();
   return visible.slice(0,3).some((value,i)=>Math.abs(value-hidden[i])>20);
 }));
 await page.screenshot({path:'/tmp/model-preview-closeup.png'});
 await page.locator('#reset').click();
 for(const id of ['rig','static']){
   await page.locator('#version').selectOption(id);await ready();
   if(id==='static')assert(await page.locator('#play').isDisabled());
 }
 for (const scale of [.001,1,1000]) {
   await page.locator('#file').setInputFiles({name:`cube-${scale}.glb`,mimeType:'model/gltf-binary',buffer:cubeGLB(scale)});await ready();
   assert.equal((await state()).clips.length,2);
   assert(await page.locator('#skeleton').isDisabled());
   await seek(.5);
   const x=await page.evaluate(()=>window.modelPreview.scene.getObjectByName('TestCube').position.x);
   assert(Math.abs(x-scale*.5)<scale*1e-5);
   await page.locator('#clip').selectOption('1');await seek(.5);
   const y=await page.evaluate(()=>window.modelPreview.scene.getObjectByName('TestCube').position.y);
   assert(Math.abs(y-scale*.5)<scale*1e-5);
   assert(await page.evaluate(()=>{const v=window.modelPreview;return v.camera.near/v.state.scale<.0001 && v.controls.minDistance/v.state.scale<=.0001}));
 }
 // Invalid upload preserves the current model and re-enables its controls.
 await page.locator('#file').setInputFiles({name:'broken.glb',mimeType:'model/gltf-binary',buffer:Buffer.from('invalid')});
 await page.waitForFunction(()=>document.getElementById('status').textContent.startsWith('Could not load'));
 assert(!(await page.locator('#play').isDisabled()));
 // Drop path, independent of the file picker.
 await page.locator('#viewport').evaluate((viewport,bytes)=>{
   const transfer=new DataTransfer();transfer.items.add(new File([new Uint8Array(bytes)],'dropped.glb'));
   viewport.dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));
 },Array.from(cubeGLB(1)));await ready();
 assert((await page.locator('#status').textContent()).includes('dropped.glb'));
 for(const path of ['/materials/review.html','/hymotion/review.html']){
   await page.goto(base+path);await ready();
   await seek(.5);
   await page.locator('#version').selectOption({index:1});await ready();
   assert.equal((await state()).time,.5);
   assert(await page.locator('#loop').isChecked());
 }
 // A compact viewport remains operable.
 await page.setViewportSize({width:390,height:844});await page.goto(base+'/preview/');await ready();
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:'/tmp/model-preview-mobile.png'});
 assert.deepEqual(errors,[]);
 console.log('PASS: variants, loop/restart/stop, static model, file picker/drop, multiple clips, 3 scales, errors, old pages, mobile and close-up camera.');
} finally {await browser.close()}
