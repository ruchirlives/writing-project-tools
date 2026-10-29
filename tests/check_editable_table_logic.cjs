// Runtime checks with an in-memory DOM and mocked browser file handles.
// These do not verify native browser permissions or visual layout.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const file=process.argv[2];if(!file)throw Error('Pass a generated synthetic HTML path.');
const html=fs.readFileSync(file,'utf8');
const initial=JSON.parse(html.match(/<script type="application\/json" id="initial">([\s\S]*?)<\/script>/)[1]);
const script=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
class Element{
 constructor(tag){this.tagName=tag;this.children=[];this.style={};this.dataset={};this._value='';this.textContent='';this.listeners={};this.hidden=false;this.files=[];this.scrollHeight=100;this.className='';this.parent=null;}
 get value(){return this._value;}set value(v){this._value=v;}
 get lastElementChild(){return this.children.at(-1);}get selectedIndex(){return this.children.findIndex(o=>o.value===this.value);}
 append(...v){for(const child of v){this.children.push(child);if(child&&typeof child==='object')child.parent=this;}if(this.tagName==='select'&&this.children.length&&this._value==='')this._value=this.children[0].value;}
 replaceChildren(...v){this.children=[];this._value='';this.append(...v);}setAttribute(k,v){this[k]=v;}
 insertBefore(n,b){const at=this.children.indexOf(b);this.children.splice(at<0?this.children.length:at,0,n);n.parent=this;}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(n=>n!==this);}
 addEventListener(k,v){this.listeners[k]=v;}
 querySelectorAll(s){const matches=n=>s==='.select-filter'?n.className.split(' ').includes('select-filter'):s==='select[data-key]'?n.tagName==='select'&&!!n.dataset.key:s==='textarea'?n.tagName==='textarea':false;const out=[];const walk=n=>{for(const c of n.children||[]){if(matches(c))out.push(c);walk(c);}};walk(this);return out;}
 querySelector(){return null;}focus(){}select(){}scrollIntoView(){}click(){this.clicked=true;}showModal(){this.open=true;}close(){this.open=false;}get outerHTML(){return '<table></table>';}
}
const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,new Element(id==='sort'?'select':'div'));return nodes.get(id);};
get('initial').textContent=JSON.stringify(initial);get('filters').append(get('search'),get('sort'),get('count'));
const storage=new Map();const context={console,JSON,Date,Set,Blob,URL,Error,Number,String,Math,Object,decodeURIComponent,document:{getElementById:get,createElement:t=>new Element(t),createTextNode:t=>({textContent:t})},window:{addEventListener(){}},localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},location:{pathname:'/review.html'},requestAnimationFrame:fn=>fn(),navigator:{},confirm:()=>true,setTimeout:()=>0};
vm.createContext(context);vm.runInContext(script,context);const run=s=>vm.runInContext(s,context),click=id=>get(id).onclick();
async function check(){
 assert.equal(get('rows').children.length,initial.rows.length);
 const first=initial.columns[0],selectCol=initial.columns.find(c=>c.type==='select');
 let input=get('rows').children[0].children[0].children.find(n=>n.tagName==='textarea');input.onfocus();input.value='Edited fictional item';input.listeners.input();assert.equal(run('data.rows[0].values.'+first.key),'Edited fictional item');click('undo');assert.equal(run('data.rows[0].values.'+first.key),initial.rows[0].values[first.key]);click('redo');
 let field=get('rows').children[0].children[initial.columns.indexOf(selectCol)].children.find(n=>n.tagName==='select');field.onfocus();field.value=selectCol.options.at(-1);field.listeners.change();assert.equal(run('data.rows[0].values.'+selectCol.key),selectCol.options.at(-1));
 const filter=get('filters').querySelectorAll('select[data-key]').find(n=>n.dataset.key===selectCol.key);filter.value=selectCol.options.at(-1);filter.onchange();assert.equal(get('rows').children.length,1);filter.value='__ALL__';filter.onchange();
 get('search').value='zzzz_no_results';get('search').oninput();assert.equal(get('rows').children.length,0);get('search').value='';get('search').oninput();
 get('rows').children[0].children.at(-1).children[0].onclick();assert.equal(get('sourceDialog').open,true);assert.ok(get('sourceBody').children.some(n=>n.className==='evidence'));click('closeSources');
 const size=run('data.rows.length');click('add');assert.equal(run('data.rows.length'),size+1);click('undo');assert.equal(run('data.rows.length'),size);
 const diskPath=path.join(path.dirname(file),'runtime-roundtrip.json');fs.writeFileSync(diskPath,JSON.stringify(initial,null,2)+'\n');
 const handle={name:path.basename(diskPath),getFile:async()=>({text:async()=>fs.readFileSync(diskPath,'utf8')}),createWritable:async()=>({write:async t=>fs.writeFileSync(diskPath,t),close:async()=>{},abort:async()=>{}})};
 context.window.showSaveFilePicker=async()=>handle;context.showSaveFilePicker=context.window.showSaveFilePicker;context.testHandle=handle;run('handle=testHandle;lastDisk='+JSON.stringify(fs.readFileSync(diskPath,'utf8')));await click('save');assert.equal(JSON.parse(fs.readFileSync(diskPath,'utf8')).rows[0].values[first.key],'Edited fictional item');assert.equal(run('dirty'),false);
 const external=JSON.parse(fs.readFileSync(diskPath,'utf8'));external.rows[0].values[first.key]='Someone else edited';fs.writeFileSync(diskPath,JSON.stringify(external));const before=fs.readFileSync(diskPath,'utf8');await click('save');assert.equal(fs.readFileSync(diskPath,'utf8'),before);assert.match(get('message').textContent,/changed elsewhere/);await click('saveAs');assert.equal(JSON.parse(fs.readFileSync(diskPath,'utf8')).rows[0].values[first.key],'Edited fictional item');
 context.reloaded=JSON.parse(fs.readFileSync(diskPath,'utf8'));run("load(reloaded,null,null,'saved.json')");assert.equal(run('data.rows[0].values.'+first.key),'Edited fictional item');
 const wrong=JSON.parse(JSON.stringify(initial));wrong.tableId='another-project';context.wrong=wrong;assert.throws(()=>run('validate(wrong)'),/companion JSON/);wrong.tableId=initial.tableId;wrong.rows[0].sourceIds=['missing'];assert.throws(()=>run('validate(wrong)'),/Invalid/);
 assert.equal(run("safeHref('javascript:alert(1)')"),null);assert.equal(run("safeHref('../notes%20and%20sources.md')"),'../notes%20and%20sources.md');
 click('copy');assert.match(get('copyText').value,/Sources and trace/);assert.equal(get('copyDialog').open,true);
 console.log('PASS: generic fields, editing, undo/redo, selection/filter/search, source trace, add/undo, save/reopen, external-change conflict, Save as, wrong-file rejection, safe links, copy preview.');
 console.log('File handles and DOM are mocked; save/reopen uses a real synthetic QA file.');
}
check().catch(e=>{console.error(e);process.exitCode=1;});
