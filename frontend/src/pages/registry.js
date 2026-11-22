import {feedback} from '../components/common/fields.js';
import {empty, panel} from '../components/common/panels.js';
import {table} from '../components/common/table.js';
import {handler} from '../hooks/action.js';
import {session} from '../stores/session.js';
import {workspace} from '../stores/workspace.js';
import {button, el, p} from '../utils/dom.js';
import {date} from '../utils/format.js';

export async function registryPage(route, refresh) {
  const {spec} = workspace;
  const items = await workspace.completions();
  const error = feedback();
  const sample = button('下载登记模板 CSV', {class:'quiet', onClick:event=>
    handler(sample,error,()=>workspace.download('/completions/template',spec.completion_sample))(event)});
  const submit = button('校验并登记', {type:'submit', class:'primary', 'data-testid':'import-completions'});
  const upload = session.canWrite && el('form',{class:'fields', onSubmit:handler(submit,error,async event=>{
    const data = new FormData(event.target);
    const file = data.get('source');
    if (!file?.size) throw new Error('请选择一个 CSV 文件');
    if (file.size > 2_000_000) throw new Error('CSV 最多 2 MB');
    await workspace.importCompletions({filename:file.name, csv_text:await file.text()});
    await refresh();
  })}, el('label',{class:'field', for:'source'}, el('span',{},'完工登记 CSV'),
    el('input',{id:'source', type:'file', name:'source', accept:'.csv,text/csv', required:true})), submit);
  const records = panel('完工登记记录', items.length ? table([
    {key:'completion_id', label:'完工单号'},
    {key:'site_id', label:'灯组编号'},
    {key:'completion_date', label:'完工日期'},
    {key:'author', label:'登记人'},
    {label:'登记时间', render:row=>date(row.created_at)},
  ], items, {caption:'完工登记记录', pageSize:16})
    : empty('还没有完工登记。请下载模板、填入完工记录后导入。'));
  return el('div',{class:'two-col'}, el('div',{class:'wide-panel'}, records),
    el('aside',{class:'sidebar-panel'},
      panel('登记导入', p('登记后立即可供新测算使用；已发起的运行沿用各自发起时的登记快照，晚到的记录只供重新测算。','subtle'),
        sample, upload, error),
      panel('登记口径', el('ul',{class:'method-list'}, spec.effect_methodology.map(text=>el('li',{},text))))));
}
