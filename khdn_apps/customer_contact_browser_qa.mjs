// Execute the shipped component JS with an instrumented DOM/message bridge.
// This checks communication and draft behavior, not physical Safari rendering.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const args = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const html = fs.readFileSync(new URL('./legacy_fast_form_component/index.html', import.meta.url), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
class Element {
  constructor(tag) {
    this.tagName = tag; this.children = []; this.listeners = new Map();
    this.dataset = {}; this.style = {setProperty() {}}; this.value = '';
    this.classList = {toggle() {}}; this.parentElement = null;
  }
  append(...nodes) { for (const n of nodes) { n.parentElement = this; this.children.push(n); } }
  appendChild(node) { this.append(node); return node; }
  replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
  setAttribute(key, value) { this[key] = String(value); }
  addEventListener(type, listener) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(listener);
  }
  contains(node) { return node === this || this.children.some(n => n.contains(node)); }
  matches(selector) { return selector.split(',').map(s => s.trim()).includes(this.tagName); }
  reportValidity() { return true; }
  getBoundingClientRect() { return {height: 160 + elements.grid.children.length * 92}; }
  dispatch(type) {
    const event = {type, target: this, preventDefault() {}};
    for (let n = this; n; n = n.parentElement)
      for (const listener of n.listeners.get(type) || []) listener(event);
  }
}
const elements = Object.fromEntries(['form','grid','submit','title','help','wrap'].map(n => [n,new Element(n === 'form' ? 'form' : 'div')]));
elements.form.append(elements.grid,elements.submit);
elements.wrap.append(elements.title,elements.help,elements.form);
const messages = [], windowHandlers = new Map();
const parent = {postMessage(message) { messages.push(message); }};
const document = {
  referrer: 'https://qa.invalid/', body: new Element('body'),
  documentElement: new Element('html'), activeElement: null,
  getElementById(id) { return elements[id]; }, querySelector() { return elements.wrap; },
  createElement(tag) { return new Element(tag); },
};
const context = vm.createContext({document,parent,URL,location:{href:'https://qa.invalid/component'},
  window:{addEventListener(type,fn) { windowHandlers.set(type,fn); }},
  queueMicrotask: fn => fn(), console, Date, Math});
vm.runInContext(script,context);
function render(params) {
  windowHandlers.get('message')({source:parent,origin:'https://qa.invalid',
    data:{type:'streamlit:render',args:params,theme:{base:'dark'}}});
}
render(args);
const state = vm.runInContext('state',context);
assert.equal(Object.keys(state).length,9);
assert.equal(state.contact_1_phone.value,args.fields.find(f => f.name === 'contact_1_phone').default);
const beforeHeights = messages.filter(m => m.type === 'streamlit:setFrameHeight').length;
for (let n = 0; n < 200; n++) {
  const input = state.contact_1_name;
  document.activeElement = input;
  input.value = 'Nội dung đang nhập QA '+n;
  input.dispatch('input'); input.dispatch('keydown'); input.dispatch('keyup'); input.dispatch('paste');
}
state.contact_1_name.dispatch('focusin');
state.contact_1_phone.value = '0987654321'; state.contact_1_phone.dispatch('input');
state.contact_1_role.value = 'Giám đốc'; state.contact_1_role.dispatch('change');
document.activeElement = state.contact_2_name; state.contact_1_name.dispatch('focusout');
render(args); // Unrelated app rerun must preserve the draft, not load defaults.
assert.equal(state.contact_1_name.value,'Nội dung đang nhập QA 199');
assert.equal(state.contact_1_phone.value,'0987654321');
assert.equal(messages.filter(m => m.type === 'streamlit:setComponentValue').length,0);
assert.equal(messages.filter(m => m.type === 'streamlit:setFrameHeight').length,beforeHeights);
assert.ok(messages.some(m => m.type === 'khdn-fast-input-focus'));
elements.form.dispatch('submit');
const submissions = messages.filter(m => m.type === 'streamlit:setComponentValue');
assert.equal(submissions.length,1);
assert.equal(Object.keys(submissions[0].value.values).length,9);
assert.equal(submissions[0].value.values.contact_1_name,'Nội dung đang nhập QA 199');
assert.equal(submissions[0].value.values.contact_1_phone,'0987654321');
assert.equal(submissions[0].value.values.contact_1_role,'Giám đốc');
assert.ok(submissions[0].value.submit_id);
const changed = structuredClone(args);
changed.resetToken = 'new-saved-contacts'; changed.fields[0].default = 'Mới lưu QA';
render(changed);
assert.equal(state.contact_1_name.value,'Mới lưu QA');
assert.equal(messages.filter(m => m.type === 'streamlit:setComponentValue').length,1);
console.log('CUSTOMER_CONTACT_BROWSER_QA_PASS 200_keys zero_value_messages_before_save phone_leading_zero local_select stable_height retained_draft one_submit nine_values new_saved_defaults');
