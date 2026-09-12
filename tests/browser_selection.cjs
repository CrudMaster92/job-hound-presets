const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../site/app.js'), 'utf8');
const elements = new Map();
const context = { TextEncoder, btoa, state: {catalog: {source_commit:'test', collections:[{id:'fortune-50-2026'}]}},
  $: id => { if (!elements.has(id)) elements.set(id, {showModal(){}}); return elements.get(id); },
  renderDrawer(){}, keyOf: (a,b)=>`${a}:${b}`, selection: (c,m)=>({company_id:c.company_id,monitor_id:m.id,revision:1}) };
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function selectable('), source.indexOf('function openJobHound(')), context);
vm.runInContext(source.slice(source.indexOf('async function openCollection('), source.indexOf('function renderDrawer(')), context);
const members = Array.from({length:237}, (_,i)=>({company_id:`company-${i}`, monitors:[{id:`monitor-${i}`,verification:{status:'verified'}}]}));
context.collectionMembers = async()=>members;
(async()=>{
  await context.openCollection('fortune-50-2026');
  assert.equal(context.state.drawer.chosen.size, 0);
  const selections = members.map(c=>context.selection(c,c.monitors[0]));
  for (const batch of [selections.slice(0,200), selections.slice(200)]) {
    const payload = JSON.parse(Buffer.from(context.encodeHandoff('collection',batch,'fortune-50-2026'),'base64url').toString());
    assert.deepEqual(payload.selections,batch);
    assert.equal(payload.collection_id,'fortune-50-2026');
  }
  assert.throws(()=>context.encodeHandoff('collection',selections,'fortune-50-2026'), /1 and 200/);
  assert.throws(()=>context.encodeHandoff('collection',[],'fortune-50-2026'), /1 and 200/);
  context.collectionMembers = async()=>members.slice(0,200);
  await context.openCollection('fortune-50-2026');
  assert.equal(context.state.drawer.chosen.size,200);
  console.log('Large collection starts empty; exact 200/37 batches; empty and oversized handoffs rejected.');
})().catch(error=>{console.error(error);process.exitCode=1;});
